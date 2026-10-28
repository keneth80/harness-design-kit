export const meta = {
  name: 'full-cycle',
  description: 'spec.md를 기준으로 architect → qa-tester → 기능별 backend/frontend → 경계 검증 → 단위 검증을 순서대로 돌린다. 중간에 멈춰도 이어서 실행된다.',
  phases: [
    { title: 'Context', detail: 'spec과 _workspace 보고서로 어디까지 됐는지 판단' },
    { title: 'Scaffold', detail: 'architect: 빌드 골격·공유 타입 (빌드 통과까지)' },
    { title: 'Tests', detail: 'qa-tester: test-cases.md와 테스트 골격' },
    { title: 'Build', detail: '기능마다 backend·frontend 병렬 구현 → qa-engineer 경계 검증 → 1회 수정' },
    { title: 'Verify', detail: 'code-verifier 최종 검증' },
  ],
}

// args: { features?: ["F1", "F3"], skipTests?: false }
const input = (args && typeof args === 'object') ? args : {}

phase('Context')
const ctx = await agent(
  `풀 사이클 진행 상황을 판단한다. 읽을 것: docs/spec.md(없으면 docs/prd.md), docs/test-cases.md, _workspace/의 보고서들.
- features: spec의 기능 ID마다 { id, title, layers }를 만든다. layers는 이 기능에 필요한 것만 ["backend"], ["frontend"], 또는 둘 다.
- architectDone: _workspace/01_architect_report.md가 있고 빌드가 통과한 상태로 끝났다고 적혀 있으면 true.
- testsDone: docs/test-cases.md가 있으면 true.
- completed: _workspace/02_*_report.md와 04_qa_engineer_report.md에서 구현과 경계 검증이 모두 끝났다고 확인되는 기능 ID.
추측하지 말고 파일에서 확인한 것만 true로 둔다.`,
  {
    label: 'context',
    effort: 'low',
    schema: {
      type: 'object',
      required: ['hasSpec', 'features', 'architectDone', 'testsDone', 'completed'],
      properties: {
        hasSpec: { type: 'boolean' },
        features: {
          type: 'array',
          items: {
            type: 'object',
            required: ['id', 'title', 'layers'],
            properties: { id: { type: 'string' }, title: { type: 'string' }, layers: { type: 'array', items: { type: 'string' } } },
          },
        },
        architectDone: { type: 'boolean' },
        testsDone: { type: 'boolean' },
        completed: { type: 'array', items: { type: 'string' } },
      },
    },
  },
)
if (!ctx) return { stopped: '진행 상황을 읽지 못했습니다.' }
if (!ctx.hasSpec) return { stopped: 'docs/spec.md(또는 prd.md)가 없습니다. /harness-full:plan-start로 기획부터 하세요.' }

const wanted = Array.isArray(input.features) && input.features.length ? new Set(input.features) : null
const todo = ctx.features.filter(f => !ctx.completed.includes(f.id) && (!wanted || wanted.has(f.id)))
log(`기능 ${ctx.features.length}개 중 남은 것 ${todo.length}개`)

if (!ctx.architectDone) {
  phase('Scaffold')
  const scaffold = await agent(
    'docs/spec.md 기준으로 빌드 설정, 도메인 엔티티, 공유 타입 골격을 만든다. 비즈니스 로직은 쓰지 않는다. ' +
    'build/install/typecheck가 통과한 상태로 끝내고 _workspace/01_architect_report.md를 쓴다. 통과 여부를 ok로 돌려준다.',
    {
      label: 'architect',
      agentType: 'harness-full:architect',
      schema: { type: 'object', required: ['ok'], properties: { ok: { type: 'boolean' }, notes: { type: 'string' } } },
    },
  )
  if (!scaffold || !scaffold.ok) {
    return { stopped: 'architect가 빌드 통과 상태를 만들지 못했습니다. dev 단계로 넘어가지 않습니다.', notes: scaffold && scaffold.notes }
  }
}

if (!ctx.testsDone && !input.skipTests) {
  phase('Tests')
  await agent(
    'docs/spec.md의 모든 기능 ID에 대해 docs/test-cases.md와 tests/ 테스트 코드를 만든다. 결과 요약을 돌려준다.',
    { label: 'qa-tester', agentType: 'harness-full:qa-tester' },
  )
}

phase('Build')
const BOUNDARY_SCHEMA = {
  type: 'object',
  required: ['high'],
  properties: {
    high: { type: 'array', items: { type: 'object', required: ['owner', 'issue'], properties: { owner: { type: 'string' }, issue: { type: 'string' } } } },
    medium: { type: 'array', items: { type: 'string' } },
  },
}
const results = []
// 기능은 하나씩 순서대로 만든다. 같은 체크아웃에서 여러 기능을 동시에 고치면 서로의 파일을 덮어쓸 수 있다.
for (const f of todo) {
  const owners = f.layers.filter(l => l === 'backend' || l === 'frontend')
  await parallel(owners.map(layer => () => agent(
    `${f.id} "${f.title}"의 ${layer === 'backend' ? '백엔드(API·비즈니스 로직·DB)' : '프론트엔드(화면·상태·API 연동)'}를 구현한다. ` +
    `docs/spec.md와 docs/test-cases.md의 ${f.id} 항목을 따르고, 공유 타입은 architect가 만든 것을 쓴다. ` +
    `${layer === 'backend' ? '프론트엔드' : '백엔드'} 파일은 건드리지 않는다. 끝나면 _workspace/02_${layer}_report.md에 ${f.id} 섹션을 추가한다.`,
    { label: `${f.id}:${layer}`, agentType: `harness-full:${layer}-dev` },
  )))

  let boundary = null
  if (owners.length === 2) {
    boundary = await agent(
      `${f.id}의 경계를 검증한다: 백엔드 응답 모델 ↔ 프론트 타입, 화면 ↔ API 매핑, 로딩·빈·에러 상태 UI. ` +
      `_workspace/04_qa_engineer_report.md에 누적 기록하고 HIGH 이슈를 owner(backend|frontend)와 함께 돌려준다.`,
      { label: `${f.id}:boundary`, agentType: 'harness-full:qa-engineer', schema: BOUNDARY_SCHEMA },
    )
    const high = (boundary && boundary.high) || []
    if (high.length) {
      log(`${f.id}: 경계 HIGH ${high.length}건 수정`)
      const byOwner = { backend: [], frontend: [] }
      for (const h of high) (byOwner[h.owner] || byOwner.backend).push(h.issue)
      await parallel(Object.entries(byOwner).filter(([, list]) => list.length).map(([layer, list]) => () => agent(
        `${f.id} 경계 검증에서 나온 HIGH 이슈를 고친다:\n${list.map((x, i) => `${i + 1}. ${x}`).join('\n')}`,
        { label: `${f.id}:fix:${layer}`, agentType: `harness-full:${layer}-dev` },
      )))
    }
  }

  const check = await agent(
    `${f.id} 관련 변경을 4개 레이어로 검증한다 (정적 분석, ${f.id} 테스트, 스펙 일치, 교훈 위반). 통과 여부와 실패 목록을 돌려준다.`,
    {
      label: `${f.id}:verify`,
      agentType: 'harness-core:code-verifier',
      schema: { type: 'object', required: ['passed'], properties: { passed: { type: 'boolean' }, failures: { type: 'array', items: { type: 'string' } } } },
    },
  )
  results.push({ id: f.id, title: f.title, boundaryHigh: ((boundary && boundary.high) || []).length, verified: !!(check && check.passed), failures: (check && check.failures) || [] })
}

phase('Verify')
const final = await agent(
  '전체 변경을 4개 레이어로 검증하고 docs/verification-report.md를 쓴다. 통과 여부와 남은 실패를 돌려준다.',
  {
    label: 'final-verify',
    agentType: 'harness-core:code-verifier',
    schema: { type: 'object', required: ['passed'], properties: { passed: { type: 'boolean' }, failures: { type: 'array', items: { type: 'string' } } } },
  },
)

return {
  features: results,
  allVerified: results.every(r => r.verified) && !!(final && final.passed),
  remaining: (final && final.failures) || [],
  next: final && final.passed
    ? '사용자에게 결과를 보고하고 실행 방법을 안내하세요.'
    : '남은 실패를 사용자에게 보고하세요. /harness-full:fix-until-green으로 이어서 고칠 수 있습니다.',
}
