#!/usr/bin/env node
// capture.mjs — harness-design 시각 점검 도구.
//
// 화면을 여러 조건(모바일·데스크톱 × 라이트·다크)으로 찍고, 사람이 눈으로 보기 전에 기계가 판정할 수 있는
// 접근성·반응형 문제를 함께 잰다. 결과 PNG는 design-critic 에이전트가 Read로 직접 본다.
//
// 사용:
//   node capture.mjs --url http://localhost:3000/ --label home [--out docs/design/shots]
//   node capture.mjs --url file:///abs/path/variant-1.html --label v1 --only desktop-light
//   node capture.mjs --config harness.config.json          (design.pages 목록을 전부)
//   결과: <out>/<label>-<viewport>-<scheme>.png, 리포트는 --config면 report.json, --url이면 <label>-report.json
//
// 측정 (페이지마다 JSON 리포트)
//   contrast   : 화면에 보이는 텍스트의 명도 대비가 WCAG AA 미만 (일반 4.5:1, 큰 글씨 3:1)
//   overflow   : 모바일에서 가로 스크롤 발생 (document 폭 > 뷰포트)
//   tapTargets : 모바일에서 24px보다 작은 버튼·링크
//   names      : 이름 없는 버튼·링크, alt 없는 이미지
//   consoleErrors : 페이지 로드 중 콘솔 에러
//   ship       : 출시 전 점검 (lang, title, description, og:image, h1 하나, <main>, 본문 바로가기, href="#" 링크,
//                한글 제목의 word-break). 페이지마다 한 번만 센다 (마감 기준 finish.md 3·4번)
//
// Playwright가 필요하다. 프로젝트의 node_modules → 전역 순서로 찾고, 없으면 설치 방법을 알려준다.

import { createRequire } from 'node:module'
import fs from 'node:fs'
import path from 'node:path'

const VIEWPORTS = {
  mobile: { width: 390, height: 844, isMobile: true, hasTouch: true, deviceScaleFactor: 2 },
  desktop: { width: 1440, height: 900, deviceScaleFactor: 1 },
}
const SCHEMES = ['light', 'dark']

function parseArgs(argv) {
  const out = { only: [] }
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]
    const next = () => argv[++i]
    if (a === '--url') out.url = next()
    else if (a === '--label') out.label = next()
    else if (a === '--out') out.out = next()
    else if (a === '--config') out.config = next()
    else if (a === '--only') out.only.push(...next().split(','))
    else if (a === '--full-page') out.fullPage = true
    else if (a === '--wait') out.wait = Number(next())
  }
  return out
}

function loadPlaywright(projectDir) {
  const tries = [path.join(projectDir, 'package.json'), import.meta.url]
  for (const base of tries) {
    try {
      return createRequire(base)('playwright')
    } catch {}
  }
  try {
    return createRequire(path.join(process.env.HOME || '/', '.npm-global', 'x.js'))('playwright')
  } catch {}
  return null
}

// 브라우저 안에서 실행: 접근성·반응형 측정
function auditInPage({ isMobile, vw }) {
  const parse = (c) => {
    const m = c.match(/rgba?\(([^)]+)\)/)
    if (!m) return null
    const [r, g, b, a = 1] = m[1].split(/[ ,/]+/).filter(Boolean).map(Number)
    return { r, g, b, a }
  }
  const lum = ({ r, g, b }) => {
    const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4 }
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
  }
  const ratio = (a, b) => { const [h, l] = [lum(a), lum(b)].sort((x, y) => y - x); return (h + 0.05) / (l + 0.05) }
  const bgOf = (el) => {
    for (let e = el; e; e = e.parentElement) {
      const c = parse(getComputedStyle(e).backgroundColor)
      if (c && c.a > 0.95) return c
      if (getComputedStyle(e).backgroundImage !== 'none') return null // 이미지·그라디언트 위 텍스트는 판정 보류
    }
    return { r: 255, g: 255, b: 255, a: 1 }
  }
  const visible = (el) => {
    const r = el.getBoundingClientRect()
    const s = getComputedStyle(el)
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && Number(s.opacity) > 0.1
  }
  const label = (el) => (el.innerText || el.getAttribute('aria-label') || el.tagName).trim().slice(0, 40)

  const contrast = []
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
  const seen = new Set()
  while (walker.nextNode()) {
    const el = walker.currentNode.parentElement
    if (!el || seen.has(el) || !walker.currentNode.textContent.trim() || !visible(el)) continue
    seen.add(el)
    const s = getComputedStyle(el)
    const fg = parse(s.color)
    const bg = bgOf(el)
    if (!fg || !bg) continue
    const size = parseFloat(s.fontSize)
    const bold = Number(s.fontWeight) >= 700
    const large = size >= 24 || (bold && size >= 18.66)
    const need = large ? 3 : 4.5
    const r = ratio(fg, bg)
    if (r < need) contrast.push({ text: label(el), ratio: Math.round(r * 100) / 100, need, fontSize: size })
    if (contrast.length >= 30) break
  }

  const names = []
  for (const el of document.querySelectorAll('button, a[href], [role=button]')) {
    if (!visible(el)) continue
    const name = (el.innerText || el.getAttribute('aria-label') || el.getAttribute('title') || '').trim()
    const imgAlt = [...el.querySelectorAll('img[alt]')].some((i) => i.alt.trim())
    if (!name && !imgAlt) names.push({ issue: '이름 없는 ' + el.tagName.toLowerCase(), html: el.outerHTML.slice(0, 80) })
  }
  for (const img of document.querySelectorAll('img')) {
    if (visible(img) && !img.hasAttribute('alt')) names.push({ issue: 'alt 없는 이미지', html: img.outerHTML.slice(0, 80) })
  }

  const tapTargets = []
  if (isMobile) {
    for (const el of document.querySelectorAll('button, a[href], input, select, [role=button]')) {
      if (!visible(el)) continue
      const r = el.getBoundingClientRect()
      if (r.width < 24 || r.height < 24) tapTargets.push({ text: label(el), size: `${Math.round(r.width)}x${Math.round(r.height)}` })
      if (tapTargets.length >= 20) break
    }
  }

  // 모바일 에뮬레이션은 넘친 콘텐츠에 맞춰 화면을 축소하므로 window.innerWidth 대신 지정한 뷰포트 폭과 비교한다
  const docWidth = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth)
  const overflow = isMobile && docWidth > vw + 1 ? { scrollWidth: docWidth, viewport: vw } : null

  // 출시 전 점검: 화면 크기·테마와 무관한 문서 수준 항목. tab.evaluate는 이 함수 본문만 브라우저로 보내므로 안에 둔다
  function shipChecks(visible) {
    const issues = []
    const add = (kind, issue) => issues.push({ kind, issue })
    const meta = (sel) => (document.querySelector(sel)?.getAttribute('content') || '').trim()
    if (!document.documentElement.lang) add('a11y', '<html lang> 없음')
    if (!document.title.trim()) add('meta', '<title> 비어 있음')
    if (!meta('meta[name="description"]')) add('meta', 'meta description 없음')
    if (!meta('meta[property="og:image"]')) add('meta', 'og:image 없음')
    const h1 = [...document.querySelectorAll('h1')].filter(visible).length
    if (h1 !== 1) add('a11y', `보이는 <h1>이 ${h1}개 (1개여야 함)`)
    if (!document.querySelector('main, [role=main]')) add('a11y', '<main> 없음')
    if (document.querySelector('nav, [role=navigation]')) {
      const focusables = [...document.querySelectorAll('a[href], button, input, select, textarea, [tabindex]:not([tabindex="-1"])')].slice(0, 3)
      if (!focusables.some((el) => el.tagName === 'A' && /^#./.test(el.getAttribute('href')))) add('a11y', '본문 바로가기 링크 없음 (내비게이션 앞 첫 포커스)')
    }
    const dead = [...document.querySelectorAll('a[href="#"]')].filter(visible).length
    if (dead) add('content', `href="#"인 링크 ${dead}개`)
    const hangul = /[\uac00-\ud7a3]/
    const broken = [...document.querySelectorAll('h1, h2, h3')]
      .filter((h) => visible(h) && hangul.test(h.textContent) && getComputedStyle(h).wordBreak !== 'keep-all')
    if (broken.length) add('typography', `한글 제목 ${broken.length}개가 word-break: keep-all이 아님 (어절 중간 줄바꿈 가능)`)
    return issues
  }

  return { contrast, names: names.slice(0, 20), tapTargets, overflow, ship: shipChecks(visible) }
}

async function capturePage(pw, page, opts, outDir) {
  const results = []
  const browser = await pw.chromium.launch()
  try {
    for (const [vpName, vp] of Object.entries(VIEWPORTS)) {
      for (const scheme of SCHEMES) {
        const key = `${vpName}-${scheme}`
        if (opts.only.length && !opts.only.includes(key)) continue
        const context = await browser.newContext({ viewport: { width: vp.width, height: vp.height }, colorScheme: scheme,
          isMobile: vp.isMobile || false, hasTouch: vp.hasTouch || false, deviceScaleFactor: vp.deviceScaleFactor })
        const tab = await context.newPage()
        const consoleErrors = []
        tab.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 200)) })
        tab.on('pageerror', (e) => consoleErrors.push(String(e).slice(0, 200)))
        let loadError = null
        try {
          await tab.goto(page.url, { waitUntil: 'networkidle', timeout: 30000 })
        } catch (e) {
          loadError = String(e).split('\n')[0]
        }
        if (opts.wait) await tab.waitForTimeout(opts.wait)
        const file = path.join(outDir, `${page.label}-${key}.png`)
        let audit = null
        if (!loadError) {
          await tab.screenshot({ path: file, fullPage: !!opts.fullPage })
          audit = await tab.evaluate(auditInPage, { isMobile: !!vp.isMobile, vw: vp.width })
        }
        results.push({ page: page.label, url: page.url, variant: key, screenshot: loadError ? null : file,
          loadError, consoleErrors: consoleErrors.slice(0, 10), ...(audit || {}) })
        await context.close()
      }
    }
  } finally {
    await browser.close()
  }
  return results
}

async function main() {
  const opts = parseArgs(process.argv.slice(2))
  const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd()
  let pages = []
  if (opts.url) pages.push({ url: opts.url, label: opts.label || 'page' })
  if (opts.config) {
    const cfg = JSON.parse(fs.readFileSync(opts.config, 'utf8'))
    pages.push(...((cfg.design && cfg.design.pages) || []))
  }
  if (!pages.length) {
    console.error('찍을 화면이 없습니다. --url 또는 harness.config.json의 design.pages를 지정하세요.')
    process.exit(2)
  }
  const pw = loadPlaywright(projectDir)
  if (!pw) {
    console.error('Playwright를 찾지 못했습니다. 프로젝트에서 `npm i -D playwright && npx playwright install chromium` 후 다시 실행하세요.')
    process.exit(3)
  }
  const outDir = path.resolve(projectDir, opts.out || 'docs/design/shots')
  fs.mkdirSync(outDir, { recursive: true })

  const all = []
  for (const page of pages) all.push(...(await capturePage(pw, page, opts, outDir)))

  const summary = {
    pages: pages.length,
    shots: all.filter((r) => r.screenshot).length,
    loadErrors: all.filter((r) => r.loadError).length,
    contrastIssues: all.reduce((n, r) => n + (r.contrast ? r.contrast.length : 0), 0),
    unnamedControls: all.reduce((n, r) => n + (r.names ? r.names.length : 0), 0),
    smallTapTargets: all.reduce((n, r) => n + (r.tapTargets ? r.tapTargets.length : 0), 0),
    mobileOverflow: all.filter((r) => r.overflow).map((r) => r.page),
    consoleErrors: all.reduce((n, r) => n + r.consoleErrors.length, 0),
    // 문서 수준 항목이라 변형 4개에서 같은 결과가 나온다. 페이지마다 첫 결과만 센다
    shipIssues: pages.reduce((n, pg) => n + ((all.find((r) => r.page === pg.label && r.ship) || {}).ship || []).length, 0),
  }
  const report = { summary, results: all }
  // 여러 시안을 같은 폴더에 찍어도 서로 덮어쓰지 않게: 단일 --url이면 <label>-report.json
  const reportName = opts.url && !opts.config ? `${opts.label || 'page'}-report.json` : 'report.json'
  report.reportFile = path.join(outDir, reportName)
  fs.writeFileSync(report.reportFile, JSON.stringify(report, null, 2))
  console.log(JSON.stringify(report, null, 2))
}

main().catch((e) => {
  console.error(String(e && e.stack || e))
  process.exit(1)
})
