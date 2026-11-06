export const meta = {
  name: 'fix-until-green',
  description: '린트·타입체크·테스트를 돌려 실패를 고치기를 반복한다. 통과 판정은 에이전트 보고가 아니라 verify_run.py의 서명된 원장으로 한다. 모두 통과하거나 두 라운드 연속 진전이 없으면 멈춘다.',
  phases: [
    { title: 'Check', detail: '검증 명령 실행과 실패 목록 수집' },
    { title: 'Fix', detail: '실패를 파일 단위로 묶어 고치기' },
    { title: 'Confirm', detail: '통과라고 나오면 다른 에이전트가 원장 상태를 다시 확인' },
  ],
}

// args: { command?: "npm test", maxRounds?: 6, verifyScript?: "<harness-core>/scripts/verify_run.py" }
const input = (args && typeof args === 'object') ? args : (args ? { command: String(args) } : {})
const MAX = Math.min(Math.max(Number(input.maxRounds) || 6, 1), 10)

// 통과 판정은 verify_run.py가 직접 돌리고 서명한 원장으로 한다. 에이전트의 "통과했다"는 말을 믿지 않는다
const VERIFY = input.verifyScript
  ? `python3 "${input.verifyScript}"`
  : `python3 "$(find ~/.claude/plugins -name verify_run.py -path '*harness-core*' 2>/dev/null | sort -V | tail -1)"`
const RUN = input.command ? `${VERIFY} --cmd ${JSON.stringify(input.command)}` : VERIFY
const OK_STATES = input.command ? ['pass', 'partial-pass'] : ['pass']

const CHECK_SCHEMA = {
  type: 'object',
  required: ['state', 'failures'],
  properties: {
    state: { type: 'string', enum: ['pass', 'partial-pass', 'fail', 'stale', 'tampered', 'missing', 'unconfigured'] },
    failures: {
      type: 'array',
      items: { type: 'object', required: ['file', 'message'], properties: { file: { type: 'string' }, message: { type: 'string' } } },
    },
  },
}
const STATUS_SCHEMA = { type: 'object', required: ['state'], properties: { state: { type: 'string' } } }

let previous = Infinity
let stalls = 0
const rounds = []
for (let round = 1; round <= MAX; round++) {
  const check = await agent(
    `다음 명령을 그대로 실행한다 (Bash 타임아웃은 넉넉히 600000ms). 코드는 고치지 않는다.\n${RUN}\n` +
    '출력 JSON의 state를 그대로 옮긴다. failures[].tail에서 실패마다 { file, message }를 만든다 ' +
    '(file을 모르면 "unknown"). 최대 60개. state를 추측하거나 바꾸지 않는다.',
    { label: `check:r${round}`, phase: 'Check', effort: 'low', schema: CHECK_SCHEMA },
  )
  if (!check) return { stopped: '검증 명령을 실행하지 못했습니다.', rounds }
  if (check.state === 'unconfigured') return { stopped: '검증 명령이 없습니다. harness.config.json의 verify를 채우세요.', rounds }
  if (check.state === 'tampered') return { stopped: '통과 기록 원장의 서명이 맞지 않습니다. 누군가 원장을 고쳤습니다. 사람이 확인해야 합니다.', rounds }
  const count = check.failures.length
  rounds.push({ round, state: check.state, failures: count })

  if (OK_STATES.includes(check.state)) {
    // 통과라고 나오면 다른 에이전트가 원장만 다시 읽는다 (검사를 돌린 쪽의 보고와 독립)
    const confirm = await agent(
      `다음 명령을 그대로 실행하고 출력 JSON의 state만 그대로 돌려준다. 다른 일은 하지 않는다.\n${VERIFY} --status`,
      { label: `confirm:r${round}`, phase: 'Confirm', model: 'haiku', effort: 'low', schema: STATUS_SCHEMA },
    )
    const confirmed = !!confirm && OK_STATES.includes(confirm.state)
    if (confirmed) return { passed: true, ledger: confirm.state, rounds }
    log(`라운드 ${round}: 통과 보고와 원장 상태가 다릅니다 (${confirm ? confirm.state : '확인 실패'}). 다시 검사합니다.`)
    rounds[rounds.length - 1].confirm = confirm ? confirm.state : null
    continue
  }

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
