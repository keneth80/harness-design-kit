export const meta = {
  name: 'domain-sweep',
  description: '모든 도메인을 매뉴얼 기준으로 동시에 진단하고, 위반마다 반박 검증을 거쳐 살아남은 것만 하나의 리포트로 모은다. 코드는 고치지 않는다.',
  phases: [
    { title: 'Discover', detail: 'docs/domains/의 매뉴얼과 code_paths 목록' },
    { title: 'Diagnose', detail: '도메인별 domain-refactor report 모드' },
    { title: 'Verify', detail: '위반마다 독립 에이전트가 반박 시도' },
    { title: 'Report', detail: 'docs/reviews/domain-sweep-<날짜>.md 작성' },
  ],
}

// args: { domains?: ["auth", "billing"] }
const input = (args && typeof args === 'object') ? args : {}

phase('Discover')
const found = await agent(
  'docs/domains/*/manual.md를 모두 찾아 도메인마다 { name, manual, codePaths, interviewStatus }를 만든다. ' +
  'codePaths는 매뉴얼 메타 블록의 code_paths 목록만 읽는다 (last_synced 같은 다른 항목을 경로로 오인하지 않는다).',
  {
    label: 'discover',
    effort: 'low',
    schema: {
      type: 'object',
      required: ['domains'],
      properties: {
        domains: {
          type: 'array',
          items: {
            type: 'object',
            required: ['name', 'manual', 'codePaths'],
            properties: {
              name: { type: 'string' }, manual: { type: 'string' },
              codePaths: { type: 'array', items: { type: 'string' } }, interviewStatus: { type: 'string' },
            },
          },
        },
      },
    },
  },
)
const wanted = Array.isArray(input.domains) && input.domains.length ? new Set(input.domains) : null
const domains = ((found && found.domains) || []).filter(d => d.codePaths.length && (!wanted || wanted.has(d.name)))
if (!domains.length) return { stopped: '진단할 도메인이 없습니다 (manual.md와 code_paths 필요).' }

const VIOLATIONS = {
  type: 'object',
  required: ['violations'],
  properties: {
    violations: {
      type: 'array',
      items: {
        type: 'object',
        required: ['rule', 'file', 'evidence', 'severity'],
        properties: {
          rule: { type: 'string' }, file: { type: 'string' }, line: { type: 'number' },
          evidence: { type: 'string' }, severity: { type: 'string', enum: ['high', 'medium', 'low'] },
        },
      },
    },
  },
}
const VERDICT = {
  type: 'object',
  required: ['isReal', 'reason'],
  properties: { isReal: { type: 'boolean' }, reason: { type: 'string' } },
}

const perDomain = await pipeline(
  domains,
  d => agent(
    `domain-refactor 스킬의 report 모드로 "${d.name}" 도메인을 진단한다. 기준: ${d.manual}의 불변 규칙(§3)과 의존 계약(§4). ` +
    `대상 코드: ${d.codePaths.join(', ')}. 코드는 고치지 않는다. 위반마다 어긴 규칙, 파일, 행, 코드 근거를 적는다. 근거 없는 추정은 넣지 않는다.`,
    { label: `diagnose:${d.name}`, phase: 'Diagnose', schema: VIOLATIONS },
  ),
  (diag, d) => parallel(((diag && diag.violations) || []).slice(0, 15).map(v => () => agent(
    `다음 "위반" 주장을 반박해 본다. 매뉴얼 ${d.manual}의 해당 규칙과 실제 코드(${v.file}${v.line ? ':' + v.line : ''})를 직접 읽고, ` +
    `정말 규칙을 어기는지 판단한다. 규칙 해석이 무리하거나 코드가 실제로는 지키고 있으면 isReal=false.\n` +
    `규칙: ${v.rule}\n근거: ${v.evidence}`,
    { label: `verify:${d.name}`, phase: 'Verify', effort: 'medium', schema: VERDICT },
  ).then(verdict => ({ domain: d.name, ...v, verdict })))),
)

const all = perDomain.flat().filter(Boolean)
const confirmed = all.filter(v => v.verdict && v.verdict.isReal)
const rejected = all.length - confirmed.length
log(`위반 후보 ${all.length}건 중 확인 ${confirmed.length}건`)

phase('Report')
const report = await agent(
  `도메인 일괄 진단 리포트를 쓴다. 파일: docs/reviews/domain-sweep-<오늘 날짜>.md (날짜는 date +%F로 얻는다).
구성: 요약(도메인별 확인된 위반 수, 심각도 분포, 반박되어 제외된 수 ${rejected}건) → 도메인별 위반 표(규칙, 파일:행, 근거, 심각도) →
매뉴얼 자체를 고쳐야 할 것 같은 신호(같은 규칙이 여러 곳에서 반복 위반되면 규칙이 현실과 안 맞을 수 있음).
확인된 위반 목록: ${JSON.stringify(confirmed.map(({ verdict, ...v }) => v))}
작성한 파일 경로만 돌려준다.`,
  { label: 'report', schema: { type: 'object', required: ['path'], properties: { path: { type: 'string' } } } },
)

return {
  domains: domains.map(d => d.name),
  candidates: all.length,
  confirmed: confirmed.length,
  bySeverity: ['high', 'medium', 'low'].reduce((o, s) => ({ ...o, [s]: confirmed.filter(v => v.severity === s).length }), {}),
  report: report && report.path,
}
