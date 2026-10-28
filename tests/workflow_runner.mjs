// 워크플로우 스크립트를 가짜 agent()로 실행해 흐름(분기·반복·집계)을 검사한다.
// 사용: node workflow_runner.mjs <workflow.js> <scenario.json>
// scenario: { "args": ..., "responses": [{ "match": "정규식(label 기준)", "reply": 값 | [값, 값, ...] }] }
//   reply가 배열이면 같은 패턴이 불릴 때마다 차례로 꺼낸다 (마지막 값은 계속 재사용).
// 출력: { "result": 반환값, "calls": [{label, agentType, phase}], "logs": [...] }
import fs from 'node:fs'

const [file, scenarioFile] = process.argv.slice(2)
const scenario = JSON.parse(fs.readFileSync(scenarioFile, 'utf8'))
const calls = []
const logs = []
const counters = new Map()
let currentPhase = null

function reply(label, opts) {
  for (const [i, r] of (scenario.responses || []).entries()) {
    if (!new RegExp(r.match).test(label)) continue
    if (!Array.isArray(r.reply)) return structuredClone(r.reply)
    const n = counters.get(i) || 0
    counters.set(i, n + 1)
    return structuredClone(r.reply[Math.min(n, r.reply.length - 1)])
  }
  return opts && opts.schema ? null : 'ok'
}

const api = {
  args: scenario.args,
  agent: async (prompt, opts = {}) => {
    const label = opts.label || prompt.slice(0, 40)
    calls.push({ label, agentType: opts.agentType || null, phase: opts.phase || currentPhase })
    return reply(label, opts)
  },
  parallel: async (thunks) => Promise.all(thunks.map((t) => Promise.resolve().then(t).catch(() => null))),
  pipeline: async (items, ...stages) => Promise.all(items.map(async (item, idx) => {
    let value = item
    for (const stage of stages) {
      try { value = await stage(value, item, idx) } catch { return null }
      if (value === null || value === undefined) return value ?? null
    }
    return value
  })),
  phase: (title) => { currentPhase = title },
  log: (msg) => logs.push(msg),
}

let src = fs.readFileSync(file, 'utf8')
const metaMatch = src.match(/export const meta = (\{[\s\S]*?\n\})/)
const meta = metaMatch ? new Function(`return ${metaMatch[1]}`)() : null
src = src.replace(/export const meta =/, 'const meta =')
// 결정성 규칙: Date.now / Math.random 금지 (런타임과 동일하게 던진다)
const guard = 'Date.now = () => { throw new Error("Date.now is not allowed") }; Math.random = () => { throw new Error("Math.random is not allowed") };'
const fn = new Function(...Object.keys(api), `return (async () => { ${guard}\n${src}\n })()`)
const result = await fn(...Object.values(api))
process.stdout.write(JSON.stringify({ meta, result, calls, logs }))
