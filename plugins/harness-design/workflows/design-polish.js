export const meta = {
  name: 'design-polish',
  description: '브리프를 바탕으로 서로 다른 시안 3개를 HTML 목업으로 만들고, 관점이 다른 심사위원 3명이 채점해 이긴 안을 2라운드 다듬는다. 실제 코드는 바꾸지 않는다.',
  phases: [
    { title: 'Directions', detail: '브리프와 현재 화면을 읽고 서로 다른 방향 N개 도출' },
    { title: 'Mockups', detail: '방향마다 독립 HTML 목업 + 4종 스크린샷·접근성 측정' },
    { title: 'Judge', detail: '브랜드 적합성·사용성·완성도 관점의 심사위원 3명이 블라인드 채점' },
    { title: 'Refine', detail: '이긴 안을 비평 → 수정 → 재촬영으로 다듬기, 마지막에 재채점' },
  ],
}

// args: { target: "다듬을 화면 설명", page?: "현재 화면 URL", variants?: 3, rounds?: 2, captureScript?: "capture.mjs 절대경로" }
const input = (args && typeof args === 'object') ? args : { target: String(args || '메인 화면') }
const TARGET = input.target || '메인 화면'
const VARIANTS = Math.min(Math.max(Number(input.variants) || 3, 2), 4)
const ROUNDS = Math.min(Math.max(Number(input.rounds) || 2, 0), 3)
const OUT = 'docs/design/variants'

// 플러그인 경로는 워크플로우 안에서 알 수 없으므로 args.captureScript로 받거나 설치 위치에서 찾는다
const FIND_CAPTURE = input.captureScript
  ? `node "${input.captureScript}"`
  : "node \"$(find ~/.claude/plugins -name capture.mjs -path '*harness-design*' 2>/dev/null | sort -V | tail -1)\""
// 마감 기준(콘텐츠·상태·솜씨) 문서도 같은 방식으로 찾는다
const FINISH_RULE = input.captureScript
  ? `마감 기준 ${input.captureScript.replace(/scripts\/capture\.mjs$/, 'skills/design-review/references/finish.md')}의 1(콘텐츠)·2(상태)·4(솜씨)를 따른다.`
  : "마감 기준 문서의 1(콘텐츠)·2(상태)·4(솜씨)를 따른다. 경로는 다음 명령으로 찾아 Read한다: find ~/.claude/plugins -name finish.md -path '*harness-design*' 2>/dev/null | sort -V | tail -1"
const SHOT_RULE = `스크린샷과 측정은 다음 명령으로 한다 (목업 경로는 pwd로 만든 절대경로):
${FIND_CAPTURE} --url file://<목업의 절대경로> --label <slug> --out ${OUT}/shots
명령이 출력한 JSON의 summary와 스크린샷 경로를 그대로 돌려준다. 명령이 실패하면 오류 메시지를 notes에 적는다.`

phase('Directions')
const plan = await agent(
  `디자인 시안을 만들기 위한 방향을 잡는다. 대상: "${TARGET}".
먼저 읽을 것: docs/design/brief.md(없으면 README·docs/spec.md로 목적을 추정하고 그 사실을 notes에 적는다),
harness.config.json의 design.tokens가 가리키는 토큰 파일, 그리고 대상 화면의 현재 코드${input.page ? `와 현재 화면(${input.page})` : ''}.
frontend-design 스킬이 있으면 그 원칙을 따른다: 주제의 세계에서 나온 선택, 템플릿 같지 않은 조합.
서로 **확실히 다른** 방향 ${VARIANTS}개를 낸다. 레이아웃 구조, 타이포의 성격, 색의 쓰임 중 최소 두 가지가 서로 달라야 한다.
하나는 브리프에 가장 충실한 안전한 안, 하나는 과감한 안으로 둔다. 브리프의 금지 사항은 어느 안도 어기지 않는다.
slug는 영문 소문자와 하이픈으로.`,
  {
    label: 'directions',
    effort: 'high',
    schema: {
      type: 'object',
      required: ['directions', 'briefFound'],
      properties: {
        briefFound: { type: 'boolean' },
        notes: { type: 'string' },
        directions: {
          type: 'array',
          minItems: 2,
          items: {
            type: 'object',
            required: ['slug', 'name', 'idea', 'layout', 'typography', 'color'],
            properties: {
              slug: { type: 'string' }, name: { type: 'string' }, idea: { type: 'string' },
              layout: { type: 'string' }, typography: { type: 'string' }, color: { type: 'string' },
              risk: { type: 'string' },
            },
          },
        },
      },
    },
  },
)
if (!plan || !plan.directions) return { stopped: '방향 도출에 실패했습니다.' }
const directions = plan.directions.slice(0, VARIANTS)
log(`방향 ${directions.length}개: ${directions.map(d => d.name).join(' / ')}`)

const MOCKUP_SCHEMA = {
  type: 'object',
  required: ['slug', 'file', 'screenshots'],
  properties: {
    slug: { type: 'string' }, file: { type: 'string' },
    screenshots: { type: 'array', items: { type: 'string' } },
    summary: { type: 'object' }, notes: { type: 'string' },
  },
}

const mockups = await pipeline(directions, d => agent(
  `"${TARGET}"의 시안 하나를 **독립 실행되는 HTML 한 파일**로 만든다: ${OUT}/${d.slug}.html
방향: ${d.name} — ${d.idea}
레이아웃: ${d.layout} / 타이포: ${d.typography} / 색: ${d.color}
규칙:
- 실제 프로젝트 코드는 건드리지 않는다. 이 HTML 파일과 스크린샷만 만든다.
- 브리프(docs/design/brief.md)의 실제 내용과 문구를 쓴다. lorem ipsum 금지. docs/design/landing-copy.md가 있으면 그 문구를 그대로 쓴다.
- ${FINISH_RULE}
- 스타일은 파일 안 <style>에 두고, 값은 CSS 변수로 정의해 쓴다 (프로젝트 토큰 파일이 있으면 그 이름을 그대로 쓰되 이 방향에 맞게 값을 정한다).
- 모바일(390px)과 데스크톱(1440px) 모두 의도적으로 배치하고, prefers-color-scheme: dark도 만든다.
- 외부 폰트는 Google Fonts <link>만 허용, 이미지는 CSS나 인라인 SVG로.
- 명도 대비 AA, 모든 버튼·링크에 이름.
${SHOT_RULE}`,
  { label: `mockup:${d.slug}`, phase: 'Mockups', schema: MOCKUP_SCHEMA },
))
const ready = mockups.filter(Boolean).filter(m => m.screenshots && m.screenshots.length)
if (ready.length < 2) return { stopped: '비교할 수 있는 시안이 2개 미만입니다.', mockups }

phase('Judge')
const LENSES = [
  { key: 'brand', focus: '브리프 적합성과 개성(기준표 1, 8번). 이 주제가 아니면 나올 수 없는 선택이 있는가, AI 기본값 냄새가 나는가' },
  { key: 'usability', focus: '위계·반응형·접근성(기준표 2, 6, 7번). 주요 과업이 바로 보이는가, 모바일에서 쓰기 편한가, report 수치' },
  { key: 'craft', focus: '타이포·색·일관성(기준표 3, 4, 5번). 크기 단계, 강조색 절제, 다크 모드 위계, 간격 리듬' },
]
// 심사위원은 이름 대신 A, B, C로만 본다 (방향 이름에 끌리지 않게)
const blind = ready.map((m, i) => ({ ...m, code: String.fromCharCode(65 + i) }))
const listing = blind.map(m => `- 시안 ${m.code}: ${m.screenshots.join(', ')}  (측정: ${JSON.stringify(m.summary || {})})`).join('\n')
const SCORE_SCHEMA = {
  type: 'object',
  required: ['scores'],
  properties: {
    scores: {
      type: 'array',
      items: {
        type: 'object',
        required: ['code', 'score', 'reason'],
        properties: {
          code: { type: 'string' }, score: { type: 'number' }, reason: { type: 'string' },
          topIssues: { type: 'array', items: { type: 'string' } },
        },
      },
    },
  },
}
const verdicts = await parallel(LENSES.map(l => () => agent(
  `디자인 시안 ${blind.length}개를 비교 채점한다. 관점: ${l.focus}.
docs/design/brief.md와 기준표를 기준으로, 각 시안의 스크린샷(PNG)을 Read로 직접 보고 1~10점을 준다.
${listing}
같은 점수를 남발하지 말고 차이를 드러낸다. 각 시안의 가장 큰 문제 3개를 topIssues에 적는다.`,
  { label: `judge:${l.key}`, agentType: 'harness-design:design-critic', schema: SCORE_SCHEMA },
)))
const totals = {}
for (const v of verdicts.filter(Boolean)) {
  for (const s of v.scores || []) totals[s.code] = (totals[s.code] || 0) + Number(s.score || 0)
}
const ranking = blind
  .map(m => ({ code: m.code, slug: m.slug, file: m.file, total: Math.round((totals[m.code] || 0) * 10) / 10 }))
  .sort((a, b) => b.total - a.total)
const winner = blind.find(m => m.code === ranking[0].code)
log(`1위: ${winner.slug} (${ranking[0].total}점)`)

phase('Refine')
const REVIEW_SCHEMA = {
  type: 'object',
  required: ['pass', 'average', 'fixes'],
  properties: {
    pass: { type: 'boolean' }, average: { type: 'number' },
    blockers: { type: 'number' }, fixes: { type: 'array', items: { type: 'string' } },
  },
}
let current = winner
const history = []
for (let round = 1; round <= ROUNDS; round++) {
  const review = await agent(
    `시안 ${current.slug}(${current.file})을 기준표 전체로 평가한다. 스크린샷: ${current.screenshots.join(', ')}.
측정: ${JSON.stringify(current.summary || {})}. pass는 기준표의 통과 기준(모든 항목 3점 이상, 평균 4점 이상, blocker 0)을 따른다.
fixes에는 다음 라운드에서 고칠 것 3개를 구체적인 값과 함께 적는다.`,
    { label: `review:r${round}`, agentType: 'harness-design:design-critic', schema: REVIEW_SCHEMA },
  )
  if (!review) break
  history.push({ round, average: review.average, pass: review.pass, fixes: review.fixes })
  if (review.pass) break
  const fixed = await agent(
    `${current.file}을 다음 세 가지만 고친다. 다른 부분은 건드리지 않는다.
${review.fixes.map((f, i) => `${i + 1}. ${f}`).join('\n')}
고친 뒤 다시 찍는다. ${SHOT_RULE}`,
    { label: `fix:r${round}`, schema: MOCKUP_SCHEMA },
  )
  if (fixed && fixed.screenshots && fixed.screenshots.length) current = { ...current, ...fixed }
}
// 마지막 라운드가 수정으로 끝났으면 고친 결과를 한 번 더 채점한다 (점수를 모른 채 끝내지 않게)
const last = history[history.length - 1]
if (last && !last.pass && history.length === ROUNDS) {
  const finalReview = await agent(
    `수정을 마친 시안 ${current.slug}(${current.file})을 기준표 전체로 다시 평가한다. 스크린샷: ${current.screenshots.join(', ')}.
측정: ${JSON.stringify(current.summary || {})}. 직전 라운드 지적이 해결됐는지 먼저 확인하고, 남은 것만 fixes에 적는다.`,
    { label: 'review:final', agentType: 'harness-design:design-critic', schema: REVIEW_SCHEMA },
  )
  if (finalReview) history.push({ round: 'final', average: finalReview.average, pass: finalReview.pass, fixes: finalReview.fixes })
}

return {
  target: TARGET,
  briefFound: plan.briefFound,
  notes: plan.notes || '',
  ranking,
  winner: { slug: current.slug, file: current.file, screenshots: current.screenshots },
  directions: directions.map(d => ({ slug: d.slug, name: d.name, idea: d.idea })),
  judges: verdicts.filter(Boolean),
  refineHistory: history,
  next: '이긴 시안을 사용자에게 보여주고, 실제 화면에 적용할지 확인받은 뒤 반영하세요 (적용 후 /harness-design:design-review).',
}
