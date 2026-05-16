"""ChromaDB + 한국어 임베딩 기반 RAG 저장소.

격리 정책:
  - admin이 ingest → 공유 컬렉션 (jarvis_docs)
  - member가 ingest → 개인 컬렉션 (jarvis_docs_user_{uid})
  - 검색 시:
      admin → 공유만
      member → 공유 + 본인 (score로 merge 후 top_k)
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.utils import embedding_functions
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.core.config import get_settings
from src.core.logger import get_logger
from src.memory.text_extractor import UnsupportedFileError, extract_text

_log = get_logger("memory.rag")

_SHARED_NAME = "jarvis_docs"
_USER_PREFIX = "jarvis_docs_user_"
_EMBED_MODEL = "jhgan/ko-sroberta-multitask"


def _user_collection_name(uid: int | str) -> str:
    return f"{_USER_PREFIX}{uid}"


@dataclass
class RetrievedDoc:
    text: str
    metadata: dict[str, Any]
    score: float

    def short(self, n: int = 80) -> str:
        return self.text[:n].replace("\n", " ")


class RagStore:
    def __init__(self, persist_dir: Path | None = None) -> None:
        settings = get_settings()
        self._persist_dir = persist_dir or settings.data_dir / "chroma"
        self._persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(self._persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=_EMBED_MODEL
        )
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=500, chunk_overlap=50
        )
        self._top_k = settings.rag_top_k
        self._score_threshold = settings.rag_score_threshold
        self._collections: dict[str, Any] = {}
        # 공유 컬렉션은 미리 워밍업
        self._get_collection(_SHARED_NAME)
        _log.info(
            f"rag ready @ {self._persist_dir} shared_count={self.count_shared()}"
        )

    def _get_collection(self, name: str):
        if name not in self._collections:
            self._collections[name] = self._client.get_or_create_collection(
                name=name,
                embedding_function=self._embed_fn,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collections[name]

    # ─── ingest ─────────────────────────────────────────
    def _ingest_to(self, coll, text: str, *, source: str, metadata: dict[str, Any] | None) -> int:
        chunks = self._splitter.split_text(text)
        if not chunks:
            return 0
        ids = [f"{source}:{i}" for i in range(len(chunks))]
        metas = [
            {"source": source, "chunk": i, **(metadata or {})}
            for i in range(len(chunks))
        ]
        coll.upsert(documents=chunks, ids=ids, metadatas=metas)
        return len(chunks)

    def ingest_for(
        self,
        text: str,
        *,
        source: str,
        owner_id: int | str,
        is_admin: bool,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[int, str]:
        """반환: (청크 수, 사용된 컬렉션 이름)."""
        name = _SHARED_NAME if is_admin else _user_collection_name(owner_id)
        coll = self._get_collection(name)
        meta = {"owner_id": str(owner_id), "is_shared": is_admin, **(metadata or {})}
        n = self._ingest_to(coll, text, source=source, metadata=meta)
        _log.info(
            f"ingest src={source} owner={owner_id} admin={is_admin} → {name} chunks={n}"
        )
        return n, name

    def ingest_file_for(
        self, path: Path, *, owner_id: int | str, is_admin: bool
    ) -> tuple[int, str]:
        if not path.exists():
            raise FileNotFoundError(path)
        # 확장자별 텍스트 추출 (UnsupportedFileError 가능)
        text = extract_text(path)
        if not text or not text.strip():
            raise UnsupportedFileError(
                f"파일에서 추출된 텍스트 없음: {path.name}"
            )
        return self.ingest_for(
            text,
            source=str(path),
            owner_id=owner_id,
            is_admin=is_admin,
            metadata={"filename": path.name, "extension": path.suffix.lower()},
        )

    # ─── query ──────────────────────────────────────────
    def _query_one(self, coll, question: str, k: int) -> list[RetrievedDoc]:
        if coll.count() == 0:
            return []
        res = coll.query(query_texts=[question], n_results=min(k, coll.count()))
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0]
        out: list[RetrievedDoc] = []
        for d, m, dist in zip(docs, metas, dists):
            score = 1.0 - float(dist)
            out.append(RetrievedDoc(text=d, metadata=m or {}, score=score))
        return out

    def query_for(
        self,
        question: str,
        *,
        user_id: int | str,
        is_admin: bool,
        top_k: int | None = None,
        score_threshold: float | None = None,
    ) -> list[RetrievedDoc]:
        k = top_k or self._top_k
        thr = score_threshold if score_threshold is not None else self._score_threshold
        shared = self._get_collection(_SHARED_NAME)
        bucket: list[RetrievedDoc] = self._query_one(shared, question, k)
        searched_personal = False
        if not is_admin:
            user_coll = self._get_collection(_user_collection_name(user_id))
            personal = self._query_one(user_coll, question, k)
            bucket.extend(personal)
            searched_personal = True
        # 점수 내림차순, top_k 자르기, threshold 필터
        bucket.sort(key=lambda h: h.score, reverse=True)
        bucket = [h for h in bucket if h.score >= thr][:k]
        _log.info(
            f"rag query user={user_id} admin={is_admin} personal={searched_personal} "
            f"hits={len(bucket)} thr={thr}"
        )
        return bucket

    # ─── counts ─────────────────────────────────────────
    def count_shared(self) -> int:
        return self._get_collection(_SHARED_NAME).count()

    def count_for_user(self, user_id: int | str) -> int:
        return self._get_collection(_user_collection_name(user_id)).count()

    # ─── delete ─────────────────────────────────────────
    def delete_by_filename(
        self,
        filename: str,
        *,
        owner_id: int | str,
        is_admin: bool,
    ) -> int:
        """metadata.filename이 일치하는 청크 제거. 반환: 제거된 청크 수.

        admin → 공유 컬렉션에서, member → 본인 컬렉션에서만 제거 가능.
        다른 사용자/공유 데이터는 절대 못 건드림.
        """
        if not filename:
            return 0
        name = _SHARED_NAME if is_admin else _user_collection_name(owner_id)
        coll = self._get_collection(name)
        if coll.count() == 0:
            return 0
        try:
            res = coll.get(where={"filename": filename})
        except Exception as e:
            _log.warning(f"delete_by_filename query failed: {e}")
            return 0
        ids = res.get("ids") or []
        if ids:
            coll.delete(ids=ids)
        _log.info(
            f"delete filename={filename} owner={owner_id} admin={is_admin} → {name} chunks={len(ids)}"
        )
        return len(ids)

    # ─── 하위 호환 (테스트/스모크용) ──────────────────────
    def ingest_text(
        self,
        text: str,
        *,
        source: str,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        n, _ = self.ingest_for(
            text, source=source, owner_id="legacy", is_admin=True, metadata=metadata
        )
        return n

    def ingest_file(self, path: Path) -> int:
        n, _ = self.ingest_file_for(path, owner_id="legacy", is_admin=True)
        return n

    def query(
        self,
        question: str,
        *,
        top_k: int | None = None,
        score_threshold: float | None = None,
    ) -> list[RetrievedDoc]:
        return self.query_for(
            question,
            user_id="legacy",
            is_admin=True,
            top_k=top_k,
            score_threshold=score_threshold,
        )

    def count(self) -> int:
        return self.count_shared()


def _smoke() -> None:
    store = RagStore()
    # admin이 공유 문서 추가
    n1, c1 = store.ingest_for(
        "JARVIS의 공유 매뉴얼: ChromaDB 사용.",
        source="admin-doc",
        owner_id=109494677,
        is_admin=True,
    )
    print(f"admin ingest → {c1}, chunks={n1}")
    # 멤버가 개인 문서 추가
    n2, c2 = store.ingest_for(
        "내 일정: 내일 회의 14시, 점심 비빔밥.",
        source="member-diary",
        owner_id=121095851,
        is_admin=False,
    )
    print(f"member ingest → {c2}, chunks={n2}")

    # admin 검색: 공유만 보임
    print("\n=== admin query (shared only) ===")
    for h in store.query_for("내 일정", user_id=109494677, is_admin=True):
        print(f"  {h.score:.2f} owner={h.metadata.get('owner_id')} | {h.short()}")
    # 멤버 검색: 공유+본인
    print("\n=== member query (shared+own) ===")
    for h in store.query_for("내 일정", user_id=121095851, is_admin=False):
        print(f"  {h.score:.2f} owner={h.metadata.get('owner_id')} | {h.short()}")
    # 다른 멤버 검색: 공유만 (남의 일정 안 보임)
    print("\n=== other member query (shared only) ===")
    for h in store.query_for("내 일정", user_id=999999, is_admin=False):
        print(f"  {h.score:.2f} owner={h.metadata.get('owner_id')} | {h.short()}")

    print(
        f"\nshared={store.count_shared()} "
        f"member1={store.count_for_user(121095851)} "
        f"member2={store.count_for_user(999999)}"
    )


if __name__ == "__main__":
    _smoke()
