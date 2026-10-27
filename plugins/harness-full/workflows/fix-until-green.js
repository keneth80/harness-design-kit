export const meta = {
  name: 'fix-until-green',
  description: '린트·타입체크·테스트를 돌려 실패를 고치기를 반복한다. 모두 통과하거나 두 라운드 연속 진전이 없으면 멈춘다.',
  phases: [
    { title: 'Check', detail: '검증 명령 실행과 실패 목록 수집' },
    { title: 'Fix', detail: '실패를 파일 단위로 묶어 고치기' },
  ],
}

// args: { command?: "npm test", maxRounds?: 6 }
const input = (args && typeof args === 'object') ? args : (args ? { command: String(args) } : {})
const MAX = Math.min(Math.max(Number(input.maxRounds) || 6, 1), 10)
const HOW = input.command
  ? `\`${input.command}\`를 실행한다.`
  : 'harness.config.json의 verify(lint, typecheck, test)를 순서대로 실행한다. 비어 있으면 package.json 스크립트·pyproject 등에서 검증 명령을 찾는다.'

const CHECK_SCHEMA = {
  type: 'object',
  required: ['passed', 'failures'],
  properties: {
    passed: { type: 'boolean' },
    commands: { type: 'array', items: { type: 'string' } },
    failures: {
      type: 'array',
      items: { type: 'object', required: ['file', 'message'], properties: { file: { type: 'string' }, message: { type: 'string' } } },
    },
  },
}

let previous = Infinity
let stalls = 0
const rounds = []
for (let round = 1; round <= MAX; round++) {
  const check = await agent(
    `${HOW} 코드는 고치지 않는다. 실패마다 { file, message }를 만든다 (file을 모르면 "unknown"). 최대 60개.`,
    { label: `check:r${round}`, phase: 'Check', effort: 'low', schema: CHECK_SCHEMA },
  )
  if (!check) return { stopped: '검증 명령을 실행하지 못했습니다.', rounds }
  const count = check.failures.length
  rounds.push({ round, failures: count })
  if (check.passed || count === 0) return { passed: true, rounds }

  stalls = count >= previous ? stalls + 1 : 0
  if (stalls >= 2) {
    return { passed: false, stopped: '두 라운드 연속 실패 수가 줄지 않았습니다. 사람이 판단해야 합니다.', rounds, remaining: check.failures.slice(0, 20) }
  }
  previous = count
  log(`라운드 ${round}: 실패 ${count}건`)

  // 같은 파일의 실패는 한 에이전트가 맡는다. 서로 다른 파일은 동시에 고친다.
  const byFile = {}
  for (const f of check.failures) (byFile[f.file] = byFile[f.file] || []).push(f.message)
  const groups = Object.entries(byFile).slice(0, 8)
  await parallel(groups.map(([file, messages]) => () => agent(
    `다음 검증 실패를 고친다. 대상 파일: ${file}\n${messages.slice(0, 10).map((m, i) => `${i + 1}. ${m}`).join('\n')}\n` +
    '원인을 고친다. 테스트를 지우거나 skip하거나, 타입을 any로 덮거나, 린트 규칙을 끄지 않는다. ' +
    '다른 파일을 고쳐야 원인이 해결되면 그 파일만 최소로 고친다.',
    { label: `fix:${file}`.slice(0, 60), phase: 'Fix' },
  )))
}
return { passed: false, stopped: `최대 ${MAX}라운드를 다 썼습니다.`, rounds }
