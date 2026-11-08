#!/usr/bin/env node
// bench_crawl: 벤치마크할 사이트의 공개 페이지를 천천히 둘러보며 "무엇을 하고 어떻게 흐르는지"를 모은다.
//
// 손님으로 가게에 들어가 동선과 메뉴판을 적어 오는 것이지, 주방(소스·자산)을 가져오는 것이 아니다.
//   - 공개 페이지만 GET으로 연다. 로그인·폼 제출·입력은 하지 않는다
//   - robots.txt를 지키고(Crawl-delay 포함), 요청 사이에 간격을 둔다. 봇 탐지를 피하는 장치는 쓰지 않는다
//   - 문구는 제목·버튼처럼 짧은 것만(80자) 남기고 본문은 길이만 잰다. 폼은 구조만(입력값은 읽지 않음)
//   - 스크린샷은 참고용이라 커밋되지 않게 shots/.gitignore를 둔다
//
// 사용:
//   node bench_crawl.mjs --url https://example.com [--url ...] [--max-pages 20] [--depth 2] [--delay 1500]
//                        [--shots 6] [--out docs/benchmark]
//   node bench_crawl.mjs --check          (Node·Playwright·Chromium 준비 점검, 안 되면 exit 3)
//
// 출력: <out>/<host>/site.json, <out>/<host>/shots/*.png. 표준 출력에는 요약 JSON 한 줄.
// 종료 코드: 0 성공, 2 인자 오류, 3 준비 안 됨, 4 robots.txt가 시작 주소를 막음

import { createRequire } from 'node:module'
import fs from 'node:fs'
import path from 'node:path'

const UA_TOKEN = 'harness-benchmark'
const USER_AGENT = `Mozilla/5.0 (compatible; ${UA_TOKEN}/1.0; +https://github.com/keneth80/harness-design-kit)`
const SKIP_EXT = /\.(pdf|zip|gz|dmg|exe|mp4|mov|mp3|wav|png|jpe?g|gif|webp|svg|ico|css|js|json|xml|rss|txt)$/i
const SKIP_PATH = /(log-?out|sign-?out|delete|remove|unsubscribe|cart\/add|checkout\/pay)/i

function parseArgs(argv) {
  const o = { urls: [], maxPages: 20, depth: 2, delay: 1500, shots: 6, out: 'docs/benchmark' }
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]
    const next = () => argv[++i]
    if (a === '--url') o.urls.push(next())
    else if (a === '--max-pages') o.maxPages = Math.min(Number(next()) || 20, 60)
    else if (a === '--depth') o.depth = Math.min(Number(next()) || 2, 4)
    else if (a === '--delay') o.delay = Math.max(Number(next()) || 1500, 500)
    else if (a === '--shots') o.shots = Math.max(Number(next()) || 0, 0)
    else if (a === '--out') o.out = next()
    else if (a === '--check') o.check = true
  }
  return o
}

function loadPlaywright(projectDir) {
  for (const base of [path.join(projectDir, 'package.json'), import.meta.url]) {
    try { return createRequire(base)('playwright') } catch {}
  }
  try { return createRequire(path.join(process.env.HOME || '/', '.npm-global', 'x.js'))('playwright') } catch {}
  return null
}

const INSTALL_HINT = '프로젝트에서 `npm i -D playwright && npx playwright install chromium` 후 다시 실행하세요. 설치하지 않으면 WebFetch만 쓰는 얕은 모드로 진행합니다.'

// robots.txt: 우리 이름의 그룹이 있으면 그것, 없으면 *. 가장 긴 규칙이 이긴다 (Allow가 같은 길이면 Allow)
export function parseRobots(text) {
  const groups = []
  let cur = null
  let lastWasAgent = false
  for (const raw of (text || '').split(/\r?\n/)) {
    const line = raw.replace(/#.*/, '').trim()
    const m = line.match(/^([A-Za-z-]+)\s*:\s*(.*)$/)
    if (!m) continue
    const key = m[1].toLowerCase()
    const val = m[2].trim()
    if (key === 'user-agent') {
      if (!lastWasAgent) { cur = { agents: [], rules: [], delay: 0 }; groups.push(cur) }
      cur.agents.push(val.toLowerCase())
      lastWasAgent = true
      continue
    }
    lastWasAgent = false
    if (!cur) continue
    if (key === 'disallow' && val) cur.rules.push({ allow: false, path: val })
    else if (key === 'allow' && val) cur.rules.push({ allow: true, path: val })
    else if (key === 'crawl-delay') cur.delay = Number(val) || 0
  }
  const pick = groups.find(g => g.agents.some(a => a !== '*' && UA_TOKEN.startsWith(a))) || groups.find(g => g.agents.includes('*'))
  return pick || { rules: [], delay: 0 }
}

export function robotsAllows(rules, pathname) {
  const toRe = (p) => new RegExp('^' + p.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*').replace(/\\\$$/, '$'))
  let best = null
  for (const r of rules) {
    if (toRe(r.path).test(pathname) && (!best || r.path.length > best.path.length || (r.path.length === best.path.length && r.allow))) best = r
  }
  return !best || best.allow
}

export function normalizeApiPath(p) {
  return p.split('/').map(seg => (/^\d+$/.test(seg) || /^[0-9a-f]{8,}$/i.test(seg) || /^[0-9a-f-]{32,36}$/i.test(seg)) ? ':id' : seg).join('/')
}

// 브라우저 안에서 실행: 페이지의 구조와 상호작용 요소. 긴 문구는 남기지 않는다
function inspectPage() {
  const clip = (s, n) => (s || '').replace(/\s+/g, ' ').trim().slice(0, n)
  const visible = (el) => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' }
  const labelOf = (el) => {
    if (el.id) { const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`); if (l) return clip(l.textContent, 40) }
    const wrap = el.closest('label'); if (wrap) return clip(wrap.textContent, 40)
    return clip(el.getAttribute('aria-label') || el.getAttribute('placeholder') || '', 40)
  }
  const headings = [...document.querySelectorAll('h1,h2,h3')].filter(visible).slice(0, 30)
    .map(h => ({ level: Number(h.tagName[1]), text: clip(h.textContent, 80) }))
  const nav = [...document.querySelectorAll('nav a[href], header a[href]')].filter(visible).slice(0, 40)
    .map(a => ({ text: clip(a.textContent || a.getAttribute('aria-label'), 40), href: a.getAttribute('href') }))
  const ctas = [...document.querySelectorAll('button, [role=button], a[class*="btn"], a[class*="button"], input[type=submit]')]
    .filter(visible).slice(0, 30).map(b => clip(b.textContent || b.value || b.getAttribute('aria-label'), 40)).filter(Boolean)
  const forms = [...document.querySelectorAll('form')].slice(0, 10).map(f => ({
    action: (() => { try { return new URL(f.getAttribute('action') || location.href, location.href).pathname } catch { return '' } })(),
    method: (f.getAttribute('method') || 'get').toLowerCase(),
    fields: [...f.querySelectorAll('input, select, textarea')].filter(i => i.type !== 'hidden').slice(0, 20)
      .map(i => ({ type: i.tagName === 'INPUT' ? (i.type || 'text') : i.tagName.toLowerCase(), name: i.name || '', label: labelOf(i), required: i.required })),
  }))
  const tech = []
  const gen = document.querySelector('meta[name=generator]')?.content; if (gen) tech.push(clip(gen, 40))
  if (window.__NEXT_DATA__ || document.getElementById('__next')) tech.push('Next.js')
  if (window.__NUXT__) tech.push('Nuxt')
  if (document.querySelector('[ng-version]')) tech.push('Angular')
  if (document.querySelector('[data-reactroot]') || document.getElementById('root')?._reactRootContainer) tech.push('React')
  if (document.querySelector('[data-v-app], #app[data-v-app]')) tech.push('Vue')
  if (document.documentElement.innerHTML.includes('wp-content')) tech.push('WordPress')
  return {
    title: clip(document.title, 80),
    lang: document.documentElement.lang || '',
    description: clip(document.querySelector('meta[name=description]')?.content, 160),
    headings, nav, ctas, forms, tech,
    landmarks: ['header', 'nav', 'main', 'footer', 'aside'].filter(t => document.querySelector(t)),
    counts: {
      links: document.querySelectorAll('a[href]').length,
      images: document.querySelectorAll('img').length,
      sections: document.querySelectorAll('section, article').length,
      textChars: (document.body?.innerText || '').length,
    },
    links: [...document.querySelectorAll('a[href]')].map(a => a.href),
  }
}

async function crawlSite(browser, start, opts, outRoot) {
  const origin = new URL(start).origin
  const host = new URL(start).host.replace(/[^a-z0-9.-]/gi, '_')
  const dir = path.join(outRoot, host)
  const shotsDir = path.join(dir, 'shots')
  fs.mkdirSync(shotsDir, { recursive: true })
  fs.writeFileSync(path.join(shotsDir, '.gitignore'), '*\n') // 남의 화면은 커밋하지 않는다

  const context = await browser.newContext({ userAgent: USER_AGENT, viewport: { width: 1280, height: 800 } })
  let robots = { rules: [], delay: 0 }
  let robotsFound = false
  try {
    const r = await context.request.get(origin + '/robots.txt', { timeout: 10000 })
    if (r.ok()) { robots = parseRobots(await r.text()); robotsFound = true }
  } catch {}
  const delay = Math.max(opts.delay, (robots.delay || 0) * 1000)
  const site = { origin, start, crawledAt: new Date().toISOString(), userAgent: USER_AGENT, robots: { found: robotsFound, rules: robots.rules.length, crawlDelay: robots.delay }, pages: [], skipped: [], api: {}, thirdParty: {} }

  if (!robotsAllows(robots.rules, new URL(start).pathname)) {
    await context.close()
    site.stopped = 'robots.txt가 시작 주소를 막습니다'
    fs.writeFileSync(path.join(dir, 'site.json'), JSON.stringify(site, null, 2))
    return { site, dir, blocked: true }
  }

  const page = await context.newPage()
  page.on('request', (req) => {
    const t = req.resourceType()
    if (t !== 'xhr' && t !== 'fetch') return
    try {
      const u = new URL(req.url())
      if (u.origin === origin) {
        const key = `${req.method()} ${normalizeApiPath(u.pathname)}`
        site.api[key] = (site.api[key] || 0) + 1
      } else {
        site.thirdParty[u.host] = (site.thirdParty[u.host] || 0) + 1
      }
    } catch {}
  })

  const queue = [{ url: start, depth: 0 }]
  const seen = new Set([start.replace(/#.*$/, '')])
  while (queue.length && site.pages.length < opts.maxPages) {
    const { url, depth } = queue.shift()
    if (site.pages.length) await page.waitForTimeout(delay)
    let status = 0
    try {
      const resp = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 20000 })
      status = resp ? resp.status() : 0
      await page.waitForTimeout(800) // 화면을 그리는 비동기 요청까지 조금 기다린다
    } catch (e) {
      site.skipped.push({ url, reason: `열기 실패: ${String(e.message || e).split('\n')[0].slice(0, 80)}` })
      continue
    }
    const info = await page.evaluate(inspectPage)
    const p = new URL(page.url())
    const entry = { url: p.origin + p.pathname, path: p.pathname, depth, status, ...info }
    delete entry.links
    if (site.pages.length < opts.shots) {
      const base = (p.pathname.replace(/[^a-z0-9]+/gi, '-').replace(/^-|-$/g, '') || 'home').slice(0, 60)
      await page.screenshot({ path: path.join(shotsDir, `${base}-desktop.png`) })
      await page.setViewportSize({ width: 390, height: 844 })
      await page.waitForTimeout(300)
      await page.screenshot({ path: path.join(shotsDir, `${base}-mobile.png`) })
      await page.setViewportSize({ width: 1280, height: 800 })
      entry.shots = [`shots/${base}-desktop.png`, `shots/${base}-mobile.png`]
    }
    site.pages.push(entry)
    if (depth >= opts.depth) continue
    for (const href of info.links) {
      let u
      try { u = new URL(href) } catch { continue }
      if (u.origin !== origin) continue
      u.hash = ''
      const hadQuery = !!u.search
      u.search = '' // 같은 페이지의 정렬·검색 변형으로 끝없이 돌지 않게
      const key = u.href
      if (seen.has(key)) continue
      seen.add(key)
      if (SKIP_EXT.test(u.pathname)) continue
      if (SKIP_PATH.test(u.pathname)) { site.skipped.push({ url: key, reason: '상태를 바꿀 수 있는 주소라 열지 않음' }); continue }
      if (!robotsAllows(robots.rules, u.pathname)) { site.skipped.push({ url: key, reason: 'robots.txt 금지' }); continue }
      queue.push({ url: key, depth: depth + 1, hadQuery })
    }
  }
  if (queue.length) site.skipped.push({ url: '(남은 링크)', reason: `최대 ${opts.maxPages}쪽에서 멈춤, ${queue.length}개 남음` })
  await context.close()
  fs.writeFileSync(path.join(dir, 'site.json'), JSON.stringify(site, null, 2))
  return { site, dir, blocked: false }
}

async function main() {
  const opts = parseArgs(process.argv.slice(2))
  const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd()
  const pw = loadPlaywright(projectDir)
  if (opts.check) {
    let chromium = false
    if (pw) { try { chromium = fs.existsSync(pw.chromium.executablePath()) } catch {} }
    const ok = !!pw && chromium
    console.log(JSON.stringify({ ok, node: process.version, playwright: !!pw, chromium, hint: ok ? '' : INSTALL_HINT }))
    process.exit(ok ? 0 : 3)
  }
  if (!opts.urls.length) { console.error('둘러볼 주소가 없습니다. --url <주소>'); process.exit(2) }
  for (const u of opts.urls) {
    try { if (!/^https?:$/.test(new URL(u).protocol)) throw new Error() } catch { console.error(`주소 형식이 아닙니다: ${u}`); process.exit(2) }
  }
  if (!pw) { console.error(`Playwright를 찾지 못했습니다. ${INSTALL_HINT}`); process.exit(3) }
  const browser = await pw.chromium.launch()
  const outRoot = path.resolve(projectDir, opts.out)
  const summary = []
  let blocked = false
  try {
    for (const u of opts.urls) {
      const r = await crawlSite(browser, u, opts, outRoot)
      blocked = blocked || r.blocked
      summary.push({
        origin: r.site.origin, dir: path.relative(projectDir, r.dir), pages: r.site.pages.length,
        skipped: r.site.skipped.length, api: Object.keys(r.site.api).length, stopped: r.site.stopped || null,
      })
    }
  } finally {
    await browser.close()
  }
  console.log(JSON.stringify({ sites: summary }))
  process.exit(blocked && summary.every(s => s.stopped) ? 4 : 0)
}

if (process.argv[1] && path.resolve(process.argv[1]) === path.resolve(new URL(import.meta.url).pathname)) main()
