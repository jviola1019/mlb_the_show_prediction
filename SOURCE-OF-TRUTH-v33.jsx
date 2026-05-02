import React, { useState, useMemo, useEffect, useRef, useCallback } from 'react';

/* ==================== QUANT MATH ==================== */
const sum = a => a.reduce((s, x) => s + x, 0);
const mean = a => a.length ? sum(a) / a.length : 0;
const std = a => { if (a.length < 2) return 0; const m = mean(a); return Math.sqrt(a.reduce((s, x) => s + (x - m) ** 2, 0) / (a.length - 1)); };
const median = a => { const s = [...a].sort((x, y) => x - y); const n = s.length; return n ? (n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2) : 0; };
const percentile = (a, p) => {
  const s = [...a].sort((x, y) => x - y); if (!s.length) return 0;
  const idx = (p / 100) * (s.length - 1); const lo = Math.floor(idx), hi = Math.ceil(idx);
  return s[lo] + (s[hi] - s[lo]) * (idx - lo);
};
const normalCDF = x => {
  const a1 = 0.254829592, a2 = -0.284496736, a3 = 1.421413741, a4 = -1.453152027, a5 = 1.061405429, p = 0.3275911;
  const sign = x < 0 ? -1 : 1; const ax = Math.abs(x) / Math.sqrt(2);
  const t = 1.0 / (1.0 + p * ax);
  const y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * Math.exp(-ax * ax);
  return 0.5 * (1.0 + sign * y);
};
const logReturns = prices => { const r = []; for (let i = 1; i < prices.length; i++) if (prices[i] > 0 && prices[i - 1] > 0) r.push(Math.log(prices[i] / prices[i - 1])); return r; };
const pearson = (x, y) => {
  if (x.length !== y.length || x.length < 2) return 0;
  const xm = mean(x), ym = mean(y); let n = 0, dx = 0, dy = 0;
  for (let i = 0; i < x.length; i++) { n += (x[i] - xm) * (y[i] - ym); dx += (x[i] - xm) ** 2; dy += (y[i] - ym) ** 2; }
  const d = Math.sqrt(dx * dy); return d > 0 ? n / d : 0;
};

// LRU cache for bootstrap forecasts (re-running analysis on same data is instant)
const __fcCache = new Map();
const __fcCacheMax = 24;
function _hashReturns(rs, current, horizon, nSims) {
  if (rs.length < 4) return `${rs.join(',')}_${current}_${horizon}_${nSims}`;
  return `${rs[0].toFixed(6)}|${rs[1].toFixed(6)}|${rs[rs.length-2].toFixed(6)}|${rs[rs.length-1].toFixed(6)}|${rs.length}|${current.toFixed(2)}|${horizon}|${nSims}`;
}

// Vectorized typed-array block bootstrap (~3-5x faster than loop version) with LRU cache
const blockBootstrap = (returns, current, horizon, nSims = 1500) => {
  if (returns.length < 8 || current <= 0) return null;
  const rsArr = returns instanceof Float64Array ? returns : Float64Array.from(returns);
  const key = _hashReturns(returns, current, horizon, nSims);
  const cached = __fcCache.get(key);
  if (cached) { __fcCache.delete(key); __fcCache.set(key, cached); return cached; }
  const N = rsArr.length;
  const L = Math.max(3, Math.round(Math.pow(N, 0.4)));
  const cols = horizon + 1;
  const buf = new Float64Array(nSims * cols);
  const logCurrent = Math.log(current);
  const maxStart = N - L + 1;
  const numBlocks = Math.ceil(horizon / L);
  for (let i = 0; i < nSims; i++) {
    buf[i * cols] = current;
    let logP = logCurrent;
    let h = 0;
    for (let bi = 0; bi < numBlocks && h < horizon; bi++) {
      const start = (Math.random() * maxStart) | 0;
      const blen = Math.min(L, horizon - h);
      for (let k = 0; k < blen; k++) {
        logP += rsArr[start + k];
        h++;
        buf[i * cols + h] = Math.exp(logP);
      }
    }
  }
  const summary = new Array(cols);
  const slice = new Float64Array(nSims);
  for (let h = 0; h <= horizon; h++) {
    for (let i = 0; i < nSims; i++) slice[i] = buf[i * cols + h];
    const sorted = Array.from(slice).sort((a, b) => a - b);
    const pct = q => {
      const idx = (q / 100) * (sorted.length - 1);
      const lo = Math.floor(idx), hi = Math.ceil(idx);
      return sorted[lo] + (sorted[hi] - sorted[lo]) * (idx - lo);
    };
    let upCount = 0;
    for (let i = 0; i < nSims; i++) if (slice[i] > current) upCount++;
    summary[h] = { p5: pct(5), p25: pct(25), p50: pct(50), p75: pct(75), p95: pct(95), pUp: upCount / nSims };
  }
  const paths = new Array(nSims);
  for (let i = 0; i < nSims; i++) {
    const row = new Array(cols);
    for (let h = 0; h < cols; h++) row[h] = buf[i * cols + h];
    paths[i] = row;
  }
  const result = { paths, summary, blockLength: L };
  if (__fcCache.size >= __fcCacheMax) __fcCache.delete(__fcCache.keys().next().value);
  __fcCache.set(key, result);
  return result;
};

const varianceRatio = (returns, k) => {
  if (returns.length < k * 2) return null;
  const v1 = std(returns) ** 2; if (v1 === 0) return null;
  const kr = []; for (let i = k - 1; i < returns.length; i++) { let s = 0; for (let j = 0; j < k; j++) s += returns[i - j]; kr.push(s); }
  return std(kr) ** 2 / (k * v1);
};

// OLS log-price ~ t with Newey-West HAC standard errors (Bartlett kernel)
const linearReg = prices => {
  const n = prices.length; if (n < 3) return null;
  const x = new Float64Array(n);
  const y = new Float64Array(n);
  for (let i = 0; i < n; i++) { x[i] = i; y[i] = Math.log(Math.max(prices[i], 1)); }
  let xm = 0, ym = 0;
  for (let i = 0; i < n; i++) { xm += x[i]; ym += y[i]; }
  xm /= n; ym /= n;
  let num = 0, den = 0;
  for (let i = 0; i < n; i++) { num += (x[i] - xm) * (y[i] - ym); den += (x[i] - xm) ** 2; }
  if (den === 0) return null;
  const slope = num / den;
  const intercept = ym - slope * xm;
  const resid = new Float64Array(n);
  let ssRes = 0, ssTot = 0;
  for (let i = 0; i < n; i++) {
    const yh = intercept + slope * x[i];
    resid[i] = y[i] - yh;
    ssRes += resid[i] * resid[i];
    ssTot += (y[i] - ym) ** 2;
  }
  const r2 = ssTot > 0 ? 1 - ssRes / ssTot : 0;
  const seNaive = Math.sqrt((ssRes / (n - 2)) / den);
  const tNaive = seNaive > 0 ? slope / seNaive : 0;
  // Newey-West HAC: lag L = floor(4*(n/100)^(2/9)), Bartlett weighting
  const L = Math.max(1, Math.floor(4 * Math.pow(n / 100, 2 / 9)));
  let omega = 0;
  for (let i = 0; i < n; i++) {
    const xi = (x[i] - xm) * resid[i];
    omega += xi * xi;
  }
  for (let l = 1; l <= L; l++) {
    let acov = 0;
    const w = 1 - l / (L + 1);
    for (let i = l; i < n; i++) acov += (x[i] - xm) * resid[i] * (x[i - l] - xm) * resid[i - l];
    omega += 2 * w * acov;
  }
  const seHAC = Math.sqrt(Math.max(0, omega) / (den * den));
  const t = seHAC > 0 ? slope / seHAC : 0;
  return { slope, r2, t, p: 2 * (1 - normalCDF(Math.abs(t))), seSlope: seHAC, seNaive, tNaive, hacLag: L };
};

const hurstExp = returns => {
  if (returns.length < 20) return null;
  const sizes = [10, 20, 40, 80, 160].filter(s => s <= Math.floor(returns.length / 2));
  if (sizes.length < 2) return null;
  const rsLog = sizes.map(n => {
    const w = Math.floor(returns.length / n); let avg = 0, valid = 0;
    for (let i = 0; i < w; i++) {
      const win = returns.slice(i * n, (i + 1) * n); const m = mean(win);
      const dev = win.map(r => r - m); const cum = []; let cs = 0;
      for (const d of dev) { cs += d; cum.push(cs); }
      const R = Math.max(...cum) - Math.min(...cum); const S = std(win);
      if (S > 0) { avg += R / S; valid++; }
    }
    return valid ? Math.log(avg / valid) : NaN;
  });
  const valid = sizes.filter((_, i) => !isNaN(rsLog[i]));
  if (valid.length < 2) return null;
  const ls = valid.map(Math.log); const rs = sizes.map((_, i) => rsLog[i]).filter(v => !isNaN(v));
  const xm = mean(ls), ym = mean(rs); let num = 0, den = 0;
  for (let i = 0; i < ls.length; i++) { num += (ls[i] - xm) * (rs[i] - ym); den += (ls[i] - xm) ** 2; }
  return den > 0 ? num / den : null;
};

// Walk-forward CV with bootstrap 90% CIs on Brier and IC
const walkForwardCV = (prices, horizon, lookback, nSimsPer = 200, bootB = 400) => {
  if (prices.length < lookback + horizon + 5) return null;
  const trades = [];
  for (let i = lookback; i < prices.length - horizon; i++) {
    const past = prices.slice(i - lookback, i + 1);
    const rs = logReturns(past); if (rs.length < 5) continue;
    const fc = blockBootstrap(rs, prices[i], horizon, nSimsPer); if (!fc) continue;
    const final = fc.paths.map(p => p[horizon]);
    const pUp = final.filter(x => x > prices[i]).length / final.length;
    const expected = mean(final.map(f => Math.log(f / prices[i])));
    const actual = Math.log(prices[i + horizon] / prices[i]);
    trades.push({ pUp, expected, actual, win: actual > 0 ? 1 : 0 });
  }
  if (!trades.length) return null;
  const eps = 1e-9;
  const brierFn = ts => { let s = 0; for (const t of ts) s += (t.pUp - t.win) ** 2; return s / ts.length; };
  const llFn = ts => { let s = 0; for (const t of ts) { const p = Math.max(eps, Math.min(1-eps, t.pUp)); s += t.win * Math.log(p) + (1-t.win) * Math.log(1-p); } return -s / ts.length; };
  const icFn = ts => pearson(ts.map(t => t.expected), ts.map(t => t.actual));
  const hitFn = ts => { let s = 0; for (const t of ts) s += t.win; return s / ts.length; };
  const brier = brierFn(trades);
  const logloss = llFn(trades);
  const ic = icFn(trades);
  const hit = hitFn(trades);
  const N = trades.length;
  const brierS = new Float64Array(bootB);
  const icS = new Float64Array(bootB);
  for (let b = 0; b < bootB; b++) {
    const sample = new Array(N);
    for (let i = 0; i < N; i++) sample[i] = trades[(Math.random() * N) | 0];
    brierS[b] = brierFn(sample); icS[b] = icFn(sample);
  }
  const ci = arr => {
    const sorted = Array.from(arr).sort((a, b) => a - b);
    return [sorted[Math.floor(0.05 * sorted.length)], sorted[Math.floor(0.95 * sorted.length)]];
  };
  return { n: N, brier, logloss, ic, hit, trades, brierCI: ci(brierS), icCI: ci(icS), bootB };
};

const pavIsotonic = (predicted, observed) => {
  const pairs = predicted.map((p, i) => [p, observed[i]]).sort((a, b) => a[0] - b[0]);
  const xs = pairs.map(p => p[0]); const ys = pairs.map(p => p[1]); const w = pairs.map(() => 1);
  let i = 0;
  while (i < ys.length - 1) {
    if (ys[i] > ys[i + 1]) {
      const nw = w[i] + w[i + 1]; ys[i] = (ys[i] * w[i] + ys[i + 1] * w[i + 1]) / nw; w[i] = nw;
      ys.splice(i + 1, 1); w.splice(i + 1, 1); xs.splice(i + 1, 1);
      if (i > 0) i--;
    } else i++;
  }
  return { xs, ys };
};
const isotonicApply = (m, p) => {
  if (!m.xs.length) return p;
  if (p <= m.xs[0]) return m.ys[0]; if (p >= m.xs[m.xs.length - 1]) return m.ys[m.ys.length - 1];
  for (let i = 0; i < m.xs.length - 1; i++) {
    if (p >= m.xs[i] && p <= m.xs[i + 1]) {
      if (m.xs[i + 1] === m.xs[i]) return m.ys[i];
      const t = (p - m.xs[i]) / (m.xs[i + 1] - m.xs[i]);
      return m.ys[i] + t * (m.ys[i + 1] - m.ys[i]);
    }
  }
  return m.ys[m.ys.length - 1];
};

const computeEV = (ask, bid, fc, horizon) => {
  if (!fc || ask <= 0) return null;
  const TAX = 0.10;
  const final = fc.paths.map(p => p[horizon]);
  const sr = bid > 0 ? bid / ask : 0.9;
  const rets = final.map(f => (f * sr * (1 - TAX) - ask) / ask);
  const er = mean(rets); const pp = rets.filter(r => r > 0).length / rets.length;
  const wins = rets.filter(r => r > 0); const losses = rets.filter(r => r < 0);
  const ws = wins.length ? mean(wins) : 0; const ls = losses.length ? -mean(losses) : 0;
  const b = ls > 0 ? ws / ls : 0;
  const k = b > 0 ? Math.max(0, (pp * b - (1 - pp)) / b) : 0;
  return { expectedRet: er, pProfit: pp, p5Ret: percentile(rets, 5), p50Ret: percentile(rets, 50), p95Ret: percentile(rets, 95), kelly: k, kellyHalf: k / 2, breakeven: ask / ((1 - TAX) * sr) };
};

/* ==================== HELPERS ==================== */
const fmtPct = (n, d = 1) => n == null || isNaN(n) ? '—' : `${(n * 100).toFixed(d)}%`;
const fmtSigned = (n, d = 1) => n == null || isNaN(n) ? '—' : `${n >= 0 ? '+' : ''}${(n * 100).toFixed(d)}%`;
const stubs = n => n == null || isNaN(n) ? '—' : `${Math.round(n).toLocaleString('en-US')}s`;

const parseListing = raw => {
  let data; try { data = typeof raw === 'string' ? JSON.parse(raw) : raw; } catch { throw new Error('Invalid JSON'); }
  const item = data.item || {};
  const ph = (data.price_history || []).map(r => {
    const ask = Number(r.best_sell_price); const bid = Number(r.best_buy_price);
    const px = !isNaN(ask) && ask > 0 ? ask : (!isNaN(bid) && bid > 0 ? bid : NaN);
    return { date: r.date || r.timestamp, px, bid, ask };
  }).filter(r => !isNaN(r.px) && r.px > 0).sort((a, b) => new Date(a.date) - new Date(b.date));
  if (!ph.length) throw new Error('No price_history');
  const askNow = Number(data.best_sell_price); const bidNow = Number(data.best_buy_price);
  return {
    name: data.listing_name || item.name || '?', rarity: item.rarity || '?', team: item.team || '?',
    ovr: item.ovr || item.rank || '?', uuid: item.uuid || '',
    askNow: !isNaN(askNow) && askNow > 0 ? askNow : ph[ph.length - 1].px,
    bidNow: !isNaN(bidNow) && bidNow > 0 ? bidNow : ph[ph.length - 1].px,
    history: ph, completed_orders: data.completed_orders || [],
  };
};

const demoData = () => {
  const out = { listing_name: 'Demo: Mike Trout', item: { uuid: 'demo', name: 'Mike Trout', rarity: 'Diamond', team: 'Angels', ovr: 92 }, price_history: [], completed_orders: [] };
  let p = 18000, prev = 0; const now = Date.now();
  for (let i = 0; i < 168; i++) {
    const drift = i > 100 ? 0.0008 : -0.0003;
    const noise = (Math.random() - 0.5) * 0.018 + 0.5 * prev; prev = noise;
    p = p * Math.exp(drift + noise);
    out.price_history.push({ date: new Date(now - (168 - i) * 3600 * 1000).toISOString(), best_sell_price: Math.round(p), best_buy_price: Math.round(p * 0.92) });
  }
  for (let j = 0; j < 80; j++) out.completed_orders.push({ date: new Date(now - Math.random() * 24 * 3600 * 1000).toISOString() });
  const last = out.price_history[out.price_history.length - 1];
  out.best_sell_price = last.best_sell_price; out.best_buy_price = last.best_buy_price;
  return JSON.stringify(out);
};

/* ==================== API + JSON PARSING ==================== */
let __lastRawResponse = null;
let __lastPrompt = null;

const callClaude = async (prompt, useSearch = true, maxTokens = 1500, useFetch = false) => {
  __lastPrompt = prompt;
  const body = { model: 'claude-sonnet-4-20250514', max_tokens: maxTokens, messages: [{ role: 'user', content: prompt }] };
  const tools = [];
  if (useSearch) tools.push({ type: 'web_search_20250305', name: 'web_search' });
  if (useFetch) tools.push({ type: 'web_fetch_20250910', name: 'web_fetch' });
  if (tools.length) body.tools = tools;
  const r = await fetch('https://api.anthropic.com/v1/messages', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  if (!r.ok) { const t = await r.text(); throw new Error(`HTTP ${r.status}: ${t.slice(0, 200)}`); }
  const data = await r.json();
  if (!data.content) throw new Error(data.error?.message || 'No content');
  const text = data.content.filter(b => b.type === 'text').map(b => b.text).join('\n');
  __lastRawResponse = text;
  return text;
};

// Robust extractor: strips markdown fences, walks balanced {...} blocks (string-aware),
// prefers candidates with expected keys; legacy regex as last resort.
const extractJSON = text => {
  if (!text || typeof text !== 'string') throw new Error('Empty response');
  const cleaned = text.replace(/```(?:json|javascript|js)?\s*/gi, '').replace(/```/g, '').trim();
  try { return JSON.parse(cleaned); } catch {}
  const candidates = [];
  let depth = 0, start = -1, inStr = false, strCh = '', prev = '';
  for (let i = 0; i < cleaned.length; i++) {
    const c = cleaned[i];
    if (inStr) { if (c === strCh && prev !== '\\') inStr = false; }
    else if (c === '"' || c === "'") { inStr = true; strCh = c; }
    else if (c === '{') { if (depth === 0) start = i; depth++; }
    else if (c === '}') {
      depth--;
      if (depth === 0 && start !== -1) { candidates.push(cleaned.slice(start, i + 1)); start = -1; }
    }
    prev = c;
  }
  let fallback = null;
  for (const cand of candidates) {
    try {
      const obj = JSON.parse(cand);
      if (obj && typeof obj === 'object' && (
        obj.results !== undefined || obj.year_used !== undefined ||
        obj.delta_ovr_predicted !== undefined || obj.consensus !== undefined
      )) return obj;
      if (!fallback && Object.keys(obj).length > 0) fallback = obj;
    } catch {}
  }
  if (fallback) return fallback;
  const m = cleaned.match(/\{[\s\S]*\}/);
  if (m) { try { return JSON.parse(m[0]); } catch {} }
  throw new Error('Invalid response format');
};

const getLastRaw = () => ({ response: __lastRawResponse, prompt: __lastPrompt });

/* ==================== GAME YEAR + NAME NORMALIZATION ==================== */
const GAME_YEARS = [26, 25, 24];  // newest first; add to head for new releases
const apiBase = (yr) => `https://mlb${yr}.theshow.com/apis`;

function normalizeName(raw) {
  if (typeof raw !== 'string') return '';
  let s = raw.trim();
  if (/^[^,]+,\s*[^,]+$/.test(s)) {
    const [last, first] = s.split(',').map(p => p.trim());
    s = `${first} ${last}`;
  }
  s = s.replace(/[\x00-\x1F\x7F]/g, '').replace(/\s+/g, ' ');
  s = s.replace(/^[.,\-\s]+/, '').replace(/[\s,\-]+$/, '');
  return s;
}

function rarityToTone(r) {
  if (!r) return 'neutral';
  const x = String(r).toLowerCase();
  if (x.includes('diamond')) return 'diamond';
  if (x.includes('gold')) return 'gold';
  if (x.includes('silver')) return 'silver';
  if (x.includes('bronze')) return 'bronze';
  return 'neutral';
}

/* ==================== CANVAS HOOKS ==================== */
const usePriceChart = (history, fc, askNow) => {
  const ref = useRef(null);
  useEffect(() => {
    const c = ref.current; if (!c || !history.length) return;
    const dpr = window.devicePixelRatio || 1;
    const rect = c.getBoundingClientRect();
    const W = rect.width, H = 200;
    c.width = W * dpr; c.height = H * dpr; c.style.height = H + 'px';
    const ctx = c.getContext('2d'); ctx.scale(dpr, dpr);
    const PL = 44, PR = 12, PT = 8, PB = 22;
    const pw = W - PL - PR, ph = H - PT - PB;
    const all = history.map(p => p.px).concat(fc ? fc.summary.map(s => s.p95).concat(fc.summary.map(s => s.p5)) : []);
    const minP = Math.min(...all), maxP = Math.max(...all);
    const range = maxP - minP || 1;
    const histN = history.length, fcN = fc ? fc.summary.length : 0;
    const totalN = histN + fcN - 1;
    const xS = i => PL + (i / Math.max(1, totalN - 1)) * pw;
    const yS = v => PT + ph * (1 - (v - minP) / range);
    ctx.fillStyle = '#050505'; ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = '#1c1c1f'; ctx.lineWidth = 1;
    for (let g = 0; g <= 4; g++) {
      const y = PT + (g / 4) * ph;
      ctx.beginPath(); ctx.moveTo(PL, y); ctx.lineTo(W - PR, y); ctx.stroke();
      ctx.fillStyle = '#52525b'; ctx.font = '9px ui-monospace,monospace'; ctx.textAlign = 'right';
      ctx.fillText(((maxP - (g / 4) * range) / 1000).toFixed(0) + 'k', PL - 4, y + 3);
    }
    if (fc) {
      const cone = fc.summary.map((s, k) => ({ x: xS(histN - 1 + k), p5: yS(s.p5), p95: yS(s.p95), p50: yS(s.p50) }));
      ctx.fillStyle = '#10b98118'; ctx.beginPath();
      cone.forEach((c, i) => i === 0 ? ctx.moveTo(c.x, c.p95) : ctx.lineTo(c.x, c.p95));
      for (let i = cone.length - 1; i >= 0; i--) ctx.lineTo(cone[i].x, cone[i].p5);
      ctx.closePath(); ctx.fill();
      ctx.strokeStyle = '#34d399'; ctx.lineWidth = 1.4; ctx.setLineDash([4, 3]);
      ctx.beginPath();
      cone.forEach((c, i) => i === 0 ? ctx.moveTo(c.x, c.p50) : ctx.lineTo(c.x, c.p50));
      ctx.stroke(); ctx.setLineDash([]);
    }
    ctx.strokeStyle = '#fafafa'; ctx.lineWidth = 1.6;
    ctx.beginPath();
    history.forEach((p, i) => i === 0 ? ctx.moveTo(xS(i), yS(p.px)) : ctx.lineTo(xS(i), yS(p.px)));
    ctx.stroke();
    ctx.strokeStyle = '#71717a'; ctx.setLineDash([2, 2]);
    ctx.beginPath(); ctx.moveTo(PL, yS(askNow)); ctx.lineTo(W - PR, yS(askNow)); ctx.stroke(); ctx.setLineDash([]);
  }, [history, fc, askNow]);
  return ref;
};

const useReliabilityChart = (pre, post) => {
  const ref = useRef(null);
  useEffect(() => {
    const c = ref.current; if (!c) return;
    const dpr = window.devicePixelRatio || 1;
    const rect = c.getBoundingClientRect();
    const W = rect.width, H = 240;
    c.width = W * dpr; c.height = H * dpr; c.style.height = H + 'px';
    const ctx = c.getContext('2d'); ctx.scale(dpr, dpr);
    const PAD = 36;
    const sz = Math.min(W - PAD * 1.5, H - PAD * 1.4);
    const ox = (W - sz) / 2, oy = PAD / 2;
    const xS = p => ox + p * sz, yS = p => oy + (1 - p) * sz;
    ctx.fillStyle = '#050505'; ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = '#1c1c1f'; ctx.lineWidth = 1;
    for (let g = 0; g <= 5; g++) {
      const t = g / 5;
      ctx.beginPath(); ctx.moveTo(xS(t), oy); ctx.lineTo(xS(t), oy + sz); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(ox, yS(t)); ctx.lineTo(ox + sz, yS(t)); ctx.stroke();
      ctx.fillStyle = '#52525b'; ctx.font = '9px ui-monospace,monospace';
      ctx.textAlign = 'right'; ctx.fillText(t.toFixed(1), ox - 3, yS(t) + 3);
      ctx.textAlign = 'center'; ctx.fillText(t.toFixed(1), xS(t), oy + sz + 12);
    }
    ctx.strokeStyle = '#71717a'; ctx.setLineDash([4, 4]); ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(xS(0), yS(0)); ctx.lineTo(xS(1), yS(1)); ctx.stroke();
    ctx.setLineDash([]);
    if (pre) pre.forEach(b => {
      const r = Math.sqrt(b.n) * 1.3;
      ctx.fillStyle = '#3b82f650'; ctx.strokeStyle = '#3b82f6'; ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.arc(xS(b.predicted), yS(b.realized), r, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    });
    if (post) post.forEach(b => {
      const r = Math.sqrt(b.n) * 1.3;
      ctx.fillStyle = '#10b98150'; ctx.strokeStyle = '#10b981'; ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.arc(xS(b.predicted), yS(b.realized), r, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    });
    ctx.fillStyle = '#71717a'; ctx.font = '10px ui-monospace,monospace'; ctx.textAlign = 'center';
    ctx.fillText('PREDICTED', ox + sz / 2, H - 6);
    ctx.save(); ctx.translate(10, oy + sz / 2); ctx.rotate(-Math.PI / 2); ctx.fillText('REALIZED', 0, 0); ctx.restore();
  }, [pre, post]);
  return ref;
};

const useViolinChart = (results) => {
  const ref = useRef(null);
  useEffect(() => {
    const c = ref.current; if (!c || !results) return;
    const dpr = window.devicePixelRatio || 1;
    const rect = c.getBoundingClientRect();
    const W = rect.width, H = 280;
    c.width = W * dpr; c.height = H * dpr; c.style.height = H + 'px';
    const ctx = c.getContext('2d'); ctx.scale(dpr, dpr);
    const tags = Object.keys(results);
    const PL = 44, PR = 12, PT = 14, PB = 36;
    const plotW = W - PL - PR, plotH = H - PT - PB;
    const yS = v => PT + plotH * (1 - v / 0.5);
    ctx.fillStyle = '#050505'; ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = '#52525b'; ctx.setLineDash([4, 4]); ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(PL, yS(0.25)); ctx.lineTo(W - PR, yS(0.25)); ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = '#71717a'; ctx.font = '9px ui-monospace,monospace'; ctx.textAlign = 'right';
    ctx.fillText('0.25', W - PR - 4, yS(0.25) - 4);
    ctx.strokeStyle = '#1c1c1f'; ctx.fillStyle = '#52525b';
    for (let v = 0; v <= 0.5; v += 0.1) {
      const y = yS(v);
      ctx.beginPath(); ctx.moveTo(PL, y); ctx.lineTo(W - PR, y); ctx.stroke();
      ctx.textAlign = 'right'; ctx.fillText(v.toFixed(2), PL - 4, y + 3);
    }
    const slotW = plotW / tags.length, colW = slotW * 0.42;
    tags.forEach((tag, ti) => {
      const cx = PL + ti * slotW + slotW / 2;
      const data = results[tag];
      ctx.fillStyle = data.color; ctx.font = 'bold 9px ui-monospace,monospace'; ctx.textAlign = 'center';
      ctx.fillText(tag, cx, H - PB + 14);
      ctx.fillStyle = '#52525b'; ctx.font = '8px ui-monospace,monospace';
      ctx.fillText('PRE  POST', cx, H - PB + 26);
      [['preAll', cx - colW * 0.5, '#3b82f6'], ['postAll', cx + colW * 0.5, '#10b981']].forEach(([key, x, dc]) => {
        const vals = data[key]; if (!vals?.length) return;
        const sorted = [...vals].sort((a, b) => a - b);
        const q1 = sorted[Math.floor(sorted.length * 0.25)];
        const med = sorted[Math.floor(sorted.length * 0.5)];
        const q3 = sorted[Math.floor(sorted.length * 0.75)];
        const min = sorted[0], max = sorted[sorted.length - 1];
        ctx.fillStyle = dc + '22'; ctx.strokeStyle = dc; ctx.lineWidth = 1;
        const bw = 16;
        ctx.fillRect(x - bw / 2, yS(q3), bw, yS(q1) - yS(q3));
        ctx.strokeRect(x - bw / 2, yS(q3), bw, yS(q1) - yS(q3));
        ctx.lineWidth = 1.5;
        ctx.beginPath(); ctx.moveTo(x - bw / 2, yS(med)); ctx.lineTo(x + bw / 2, yS(med)); ctx.stroke();
        ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(x, yS(q3)); ctx.lineTo(x, yS(max)); ctx.moveTo(x, yS(q1)); ctx.lineTo(x, yS(min)); ctx.stroke();
        ctx.fillStyle = dc;
        vals.forEach((v, i) => {
          const jit = ((i * 9301 + 49297) % 233280) / 233280 - 0.5;
          ctx.beginPath(); ctx.arc(x + jit * (bw - 3), yS(v), 1.6, 0, Math.PI * 2); ctx.fill();
        });
      });
    });
    ctx.save(); ctx.translate(12, H / 2); ctx.rotate(-Math.PI / 2);
    ctx.fillStyle = '#71717a'; ctx.font = '10px ui-monospace,monospace'; ctx.textAlign = 'center'; ctx.fillText('BRIER', 0, 0);
    ctx.restore();
  }, [results]);
  return ref;
};

/* ==================== UI PRIMITIVES ==================== */
const Pill = ({ tone = 'neutral', children }) => {
  const tones = {
    bull: 'bg-emerald-950 text-emerald-300 border-emerald-800',
    bear: 'bg-rose-950 text-rose-300 border-rose-800',
    warn: 'bg-amber-950 text-amber-300 border-amber-800',
    info: 'bg-sky-950 text-sky-300 border-sky-800',
    neutral: 'bg-zinc-900 text-zinc-300 border-zinc-700',
    diamond: 'bg-blue-950 text-blue-300 border-blue-800',
    gold: 'bg-amber-950 text-amber-300 border-amber-700',
    silver: 'bg-zinc-900 text-zinc-200 border-zinc-600',
    bronze: 'bg-orange-950 text-orange-300 border-orange-800',
  };
  return <span className={`inline-block text-[9px] font-mono uppercase tracking-wider px-2 py-0.5 border rounded mr-1 mb-1 ${tones[tone] || tones.neutral}`}>{children}</span>;
};
const Stat = ({ label, value, sub, accent = '' }) => (
  <div className="border border-zinc-800 bg-black p-2 rounded">
    <div className="text-[9px] uppercase tracking-widest text-zinc-500 font-mono">{label}</div>
    <div className={`text-base font-mono font-bold mt-0.5 ${accent}`}>{value}</div>
    {sub && <div className="text-[9px] text-zinc-500 font-mono">{sub}</div>}
  </div>
);


// Roster update awareness — known schedule for MLB The Show 26 (manually maintained from showdd.io)
// Update this list as new updates ship; the banner picks the next future date automatically.
const ROSTER_UPDATES = [
  // [ISO date, type ('transaction'|'attribute'), notes]
  ['2026-03-27', 'attribute', 'launch update — 31 changes'],
  ['2026-04-03', 'transaction', 'weekly tx'],
  ['2026-04-10', 'transaction', 'weekly tx'],
  ['2026-04-17', 'transaction', 'weekly tx'],
  ['2026-04-24', 'attribute', 'update #3 — 19 changes'],
  ['2026-05-01', 'transaction', 'weekly tx'],
  ['2026-05-08', 'transaction', 'weekly tx'],
  ['2026-05-15', 'attribute', 'attribute update window'],
  ['2026-05-22', 'transaction', 'weekly tx'],
  ['2026-05-29', 'transaction', 'weekly tx'],
  ['2026-06-05', 'attribute', 'attribute update window'],
];

function RosterUpdateBanner() {
  const todayISO = new Date().toISOString().slice(0, 10);
  const past = ROSTER_UPDATES.filter(([d]) => d <= todayISO);
  const future = ROSTER_UPDATES.filter(([d]) => d > todayISO);
  const last = past[past.length - 1];
  const next = future[0];
  if (!next) return null;
  const daysUntil = Math.ceil((new Date(next[0]) - new Date(todayISO)) / 86400000);
  const isToday = daysUntil === 0;
  const isImminent = daysUntil <= 2;
  const isAttribute = next[1] === 'attribute';
  return (
    <section className={`border rounded p-2.5 ${isAttribute ? 'border-amber-700 bg-amber-950/20' : 'border-zinc-800 bg-zinc-950'}`}>
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="text-[9px] font-mono tracking-widest text-zinc-500">ROSTER UPDATE</div>
          <div className={`text-xs font-mono font-bold mt-0.5 ${isAttribute ? 'text-amber-300' : 'text-zinc-200'}`}>
            {isToday ? 'TODAY' : `IN ${daysUntil}D`} · {next[1].toUpperCase()}
          </div>
          <div className="text-[9px] font-mono text-zinc-500 mt-0.5">
            next: {next[0]} ({next[2]}) · last: {last ? last[0] : '—'}
          </div>
        </div>
        {isAttribute && (
          <div className="text-right">
            <Pill tone="warn">ATTR</Pill>
          </div>
        )}
        {!isAttribute && isImminent && (
          <div className="text-right">
            <Pill tone="info">SOON</Pill>
          </div>
        )}
      </div>
    </section>
  );
}

/* ==================== TABS ==================== */
function CardTab() {
  const [name, setName] = useState('');
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState(null);
  const [searchError, setSearchError] = useState('');
  const [uuid, setUuid] = useState('');
  const [raw, setRaw] = useState('');
  const [parsed, setParsed] = useState(null);
  const [parseError, setParseError] = useState('');
  const [llmResult, setLlmResult] = useState(null);
  const [llmStatus, setLlmStatus] = useState('idle');
  const [llmError, setLlmError] = useState('');

  const [activeYear, setActiveYear] = useState(GAME_YEARS[0]);
  const [showDebug, setShowDebug] = useState(false);

  const apiUrl = uuid.trim() && /^[a-f0-9]{32}$/i.test(uuid.trim())
    ? `${apiBase(activeYear)}/listing.json?uuid=${uuid.trim().toLowerCase()}`
    : '';

  const doSearch = () => {
    const q = normalizeName(name);
    if (!q || q.length < 2) {
      setSearchError('Enter at least 2 characters');
      return;
    }
    setSearchError('');
    // Build tap-out search URLs — these work on iPhone Safari with no auth
    const enc = encodeURIComponent(q);
    setSearchResults({
      query: q,
      links: [
        { name: 'mlb26.theshow.com market', url: `https://mlb${activeYear}.theshow.com/community_market?name=${enc}`, primary: true },
        { name: 'showzone.gg cards', url: `https://showzone.gg/cards?q=${enc}` },
        { name: 'theshowbase.com players', url: `https://www.theshowbase.com/players?search=${enc}` },
        { name: 'showdd.io players', url: `https://www.showdd.io/players?q=${enc}` },
      ],
    });
  };

  const handleParse = () => {
    setParseError(''); setLlmResult(null);
    try { setParsed(parseListing(raw)); }
    catch (e) { setParseError(e.message); setParsed(null); }
  };

  const analysis = useMemo(() => {
    if (!parsed) return null;
    const prices = parsed.history.map(h => h.px);
    const dates = parsed.history.map(h => h.date);
    const deltas = []; for (let i = 1; i < dates.length; i++) deltas.push((new Date(dates[i]) - new Date(dates[i - 1])) / 3600000);
    const stepHours = deltas.length ? Math.max(0.1, median(deltas)) : 1;
    const stepsPerDay = Math.max(1, Math.round(24 / stepHours));
    const stepsPerWeek = stepsPerDay * 7;
    const rs = logReturns(prices);
    const fcMain = blockBootstrap(rs, parsed.askNow, stepsPerWeek, 1500);
    const horizons = [{ label: '1d', steps: stepsPerDay }, { label: '3d', steps: stepsPerDay * 3 }, { label: '7d', steps: stepsPerWeek }];
    const evByH = horizons.map(h => { const fc = blockBootstrap(rs, parsed.askNow, h.steps, 1000); return { ...h, ev: computeEV(parsed.askNow, parsed.bidNow, fc, h.steps) }; });
    const reg = linearReg(prices);
    const hurst = hurstExp(rs);
    const m30 = prices.slice(-Math.min(30, prices.length));
    const z30 = std(m30) > 0 ? (parsed.askNow - mean(m30)) / std(m30) : 0;
    const m7 = prices.slice(-Math.min(stepsPerWeek, prices.length));
    const mom7 = m7.length > 1 ? (m7[m7.length - 1] - m7[0]) / m7[0] : 0;
    const volAnn = std(rs) * Math.sqrt((365 * 24) / stepHours);
    const spreadPct = parsed.askNow > 0 ? (parsed.askNow - parsed.bidNow) / parsed.askNow : 0;
    const wfH = Math.min(stepsPerWeek, Math.floor(prices.length / 4));
    const wfL = Math.min(40, Math.floor(prices.length / 2));
    const wfcv = walkForwardCV(prices, wfH, wfL, 200);
    let calib = null;
    if (wfcv && wfcv.trades.length >= 20) {
      const half = Math.floor(wfcv.trades.length / 2);
      const tP = wfcv.trades.slice(0, half).map(t => t.pUp);
      const tW = wfcv.trades.slice(0, half).map(t => t.win);
      const map = pavIsotonic(tP, tW);
      const test = wfcv.trades.slice(half);
      const calP = test.map(t => isotonicApply(map, t.pUp));
      const realW = test.map(t => t.win);
      const bPre = mean(test.map(t => (t.pUp - t.win) ** 2));
      const bPost = mean(calP.map((p, i) => (p - realW[i]) ** 2));
      const buckets = (probs, wins) => {
        const out = [];
        for (const [lo, hi] of [[0, 0.2], [0.2, 0.4], [0.4, 0.6], [0.6, 0.8], [0.8, 1.001]]) {
          const inB = probs.map((p, i) => [p, wins[i]]).filter(([p]) => p >= lo && p < hi);
          if (inB.length) out.push({ predicted: mean(inB.map(x => x[0])), realized: mean(inB.map(x => x[1])), n: inB.length });
        }
        return out;
      };
      calib = { brierPre: bPre, brierPost: bPost, bucketsPre: buckets(test.map(t => t.pUp), realW), bucketsPost: buckets(calP, realW), improved: bPost < bPre };
    }
    let score = 0; const flags = [];
    const ev7 = evByH[2].ev;
    if (ev7?.expectedRet > 0.05) { score += 2; flags.push(['+EV>5%', 'bull']); }
    else if (ev7?.expectedRet > 0.01) { score += 1; flags.push(['+EV', 'bull']); }
    else if (ev7?.expectedRet < -0.05) { score -= 2; flags.push(['-EV<-5%', 'bear']); }
    else if (ev7?.expectedRet < -0.01) { score -= 1; flags.push(['-EV', 'bear']); }
    if (reg?.p < 0.05 && reg.slope > 0) { score += 1; flags.push(['drift sig+', 'bull']); }
    if (reg?.p < 0.05 && reg.slope < 0) { score -= 1; flags.push(['drift sig-', 'bear']); }
    if (z30 < -1.5) { score += 1; flags.push(['oversold', 'bull']); }
    if (z30 > 1.5) { score -= 1; flags.push(['overbought', 'bear']); }
    if (hurst > 0.6) flags.push(['trending', 'info']);
    if (hurst < 0.4) flags.push(['mean-revert', 'info']);
    if (spreadPct > 0.15) { score -= 1; flags.push(['wide spread', 'warn']); }
    if (wfcv && wfcv.icCI && wfcv.icCI[1] < 0) flags.push(['CV IC<0 (sig)', 'warn']);
    else if (wfcv && wfcv.ic < -0.1) flags.push(['CV IC<0', 'warn']);
    let action = 'HOLD', tone = 'neutral';
    if (score >= 3) { action = 'STRONG BUY'; tone = 'bull'; }
    else if (score >= 1) { action = 'BUY'; tone = 'bull'; }
    else if (score <= -3) { action = 'STRONG SELL'; tone = 'bear'; }
    else if (score <= -1) { action = 'SELL'; tone = 'bear'; }
    return { stepHours, fcMain, evByH, reg, hurst, z30, mom7, volAnn, spreadPct, wfcv, calib, action, tone, score, flags };
  }, [parsed]);

  const priceCanvasRef = usePriceChart(parsed?.history || [], analysis?.fcMain, parsed?.askNow);
  const reliabilityRef = useReliabilityChart(analysis?.calib?.bucketsPre, analysis?.calib?.bucketsPost);

  const fetchConsensus = () => {};

  const toneClass = analysis?.tone === 'bull' ? 'text-emerald-400' : analysis?.tone === 'bear' ? 'text-rose-400' : 'text-zinc-300';

  return (
    <div className="space-y-3">
      <RosterUpdateBanner />
      <section className="border border-zinc-800 rounded bg-zinc-950 p-3">
        <div className="text-[9px] font-mono tracking-widest text-zinc-500 mb-2">01 · FIND CARD</div>
        <div className="flex gap-1.5">
          <input value={name} onChange={e => setName(e.target.value)} onKeyDown={e => e.key === 'Enter' && doSearch()}
            placeholder="player name (any caps)" autoCapitalize="words" autoCorrect="off" spellCheck="false"
            className="flex-1 bg-black border border-zinc-800 px-2 py-2 text-xs font-mono text-zinc-200 rounded focus:border-emerald-700 outline-none" />
          <button onClick={doSearch} disabled={!name.trim() || searching} className="px-3 py-2 text-[11px] font-mono font-bold bg-emerald-600 text-black rounded disabled:bg-zinc-800 disabled:text-zinc-600">
            {searching ? '...' : 'SEARCH'}
          </button>
        </div>
        {searchError && (
          <div className="text-[10px] font-mono mt-1 flex items-center gap-2 flex-wrap">
            <span className="text-rose-400">{searchError}</span>
            <button onClick={doSearch} className="text-[9px] px-2 py-0.5 border border-zinc-700 text-zinc-300 rounded hover:border-emerald-700 hover:text-emerald-400">RETRY</button>
            <button onClick={() => setShowDebug(s => !s)} className="text-[9px] px-2 py-0.5 border border-zinc-700 text-zinc-300 rounded hover:border-amber-600 hover:text-amber-400">{showDebug ? 'HIDE' : 'DEBUG'}</button>
          </div>
        )}
        {showDebug && (
          <div className="mt-2 border border-amber-700 bg-amber-950/30 p-2 rounded">
            <div className="text-[9px] font-mono text-amber-400 tracking-widest mb-1">DEBUG · LAST RESPONSE ({(getLastRaw().response || '').length} chars)</div>
            <pre className="text-[9px] font-mono text-amber-200 max-h-40 overflow-y-auto whitespace-pre-wrap break-words m-0">{(getLastRaw().response || '(no response yet)').slice(0, 2000)}</pre>
            <div className="text-[9px] font-mono text-zinc-500 tracking-widest mt-2 mb-1">PROMPT</div>
            <pre className="text-[9px] font-mono text-zinc-400 max-h-24 overflow-y-auto whitespace-pre-wrap break-words m-0">{(getLastRaw().prompt || '').slice(0, 600)}</pre>
          </div>
        )}
        {searchResults?.links && (
          <div className="mt-2 space-y-1.5">
            <div className="text-[9px] font-mono text-zinc-500">
              <span className="text-emerald-400">●</span> Tap to search "{searchResults.query}" externally · MLB{activeYear}
            </div>
            {searchResults.links.map((l, i) => (
              <a key={i} href={l.url} target="_blank" rel="noopener noreferrer"
                className={`block w-full text-left p-2 border rounded transition-colors ${l.primary ? 'bg-emerald-950/30 border-emerald-800 hover:border-emerald-600' : 'bg-black border-zinc-800 hover:border-emerald-700'}`}>
                <div className={`font-mono text-xs ${l.primary ? 'text-emerald-300' : 'text-zinc-200'}`}>{l.name} →</div>
              </a>
            ))}
            <div className="text-[9px] font-mono text-zinc-500 mt-1">
              ① Find your card · ② Tap card → copy URL · ③ Paste UUID below or tap OPEN JSON · ④ Paste JSON response
            </div>
          </div>
        )}
      </section>

      <section className="border border-zinc-800 rounded bg-zinc-950 p-3">
        <div className="text-[9px] font-mono tracking-widest text-zinc-500 mb-2">02 · INGEST listing.json</div>
        <input value={uuid} onChange={e => setUuid(e.target.value)} placeholder="UUID (or use search)"
          className="w-full bg-black border border-zinc-800 px-2 py-2 text-xs font-mono text-zinc-200 rounded focus:border-emerald-700 outline-none" />
        <div className="flex gap-1.5 mt-2 flex-wrap">
          <a href={apiUrl || `https://mlb${activeYear}.theshow.com/community_market`} target="_blank" rel="noopener noreferrer"
            className={`text-[10px] font-mono px-2 py-1 border rounded ${apiUrl ? 'bg-emerald-950 border-emerald-700 text-emerald-300' : 'bg-zinc-900 border-zinc-700 text-zinc-400'}`}>
            {apiUrl ? 'OPEN JSON →' : 'BROWSE MARKET →'}
          </a>
          <button onClick={() => setRaw(demoData())} className="text-[10px] font-mono px-2 py-1 bg-zinc-900 border border-zinc-700 text-zinc-300 rounded">LOAD DEMO</button>
          {raw && <button onClick={() => { setRaw(''); setParsed(null); setUuid(''); }} className="text-[10px] font-mono px-2 py-1 bg-zinc-900 border border-zinc-700 text-zinc-400 rounded">CLEAR</button>}
        </div>
        <textarea value={raw} onChange={e => setRaw(e.target.value)} rows={3} placeholder='paste {"listing_name":...,"price_history":[...]}'
          className="w-full mt-2 bg-black border border-zinc-800 px-2 py-2 text-[10px] font-mono text-zinc-200 rounded focus:border-emerald-700 outline-none resize-y" />
        <div className="flex items-center gap-2 mt-2">
          <button onClick={handleParse} disabled={!raw} className="px-3 py-1.5 text-[11px] font-mono font-bold bg-emerald-600 text-black rounded disabled:bg-zinc-800 disabled:text-zinc-600">PARSE & ANALYZE</button>
          {parseError && <span className="text-[10px] text-rose-400 font-mono">{parseError}</span>}
        </div>
      </section>

      {parsed && analysis && (
        <>
          <section className="border border-zinc-800 rounded bg-zinc-950 p-3">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0 flex-1">
                <div className="text-[9px] font-mono tracking-widest text-zinc-500">03 · TARGET</div>
                <div className="text-base font-mono font-bold truncate">{parsed.name}</div>
                <div className="mt-1"><Pill>{parsed.rarity}</Pill><Pill>{parsed.team}</Pill><Pill>OVR {parsed.ovr}</Pill><Pill>N={parsed.history.length}</Pill></div>
              </div>
              <div className="text-right shrink-0">
                <div className="text-[9px] font-mono text-zinc-500 tracking-widest">SIGNAL</div>
                <div className={`text-xl font-mono font-extrabold ${toneClass}`}>{analysis.action}</div>
                <div className="text-[9px] font-mono text-zinc-500">score {analysis.score >= 0 ? '+' : ''}{analysis.score}</div>
              </div>
            </div>
            <div className="mt-2">{analysis.flags.map(([t, tn], i) => <Pill key={i} tone={tn}>{t}</Pill>)}</div>
          </section>

          <div className="grid grid-cols-3 gap-1.5">
            <Stat label="ASK" value={stubs(parsed.askNow)} sub="you pay" accent="text-rose-300" />
            <Stat label="BID" value={stubs(parsed.bidNow)} sub="you receive" accent="text-emerald-300" />
            <Stat label="SPREAD" value={fmtPct(analysis.spreadPct)} sub={stubs(parsed.askNow - parsed.bidNow)} accent={analysis.spreadPct > 0.15 ? 'text-amber-300' : ''} />
          </div>

          <section className="border border-zinc-800 rounded bg-zinc-950 p-3">
            <div className="text-[9px] font-mono tracking-widest text-zinc-500 mb-2">04 · PRICE PATH + 1W FORECAST</div>
            <canvas ref={priceCanvasRef} style={{ width: '100%', display: 'block' }} />
            <div className="text-[9px] font-mono text-zinc-500 mt-1">block bootstrap, L={analysis.fcMain?.blockLength}</div>
          </section>

          <section className="border border-zinc-800 rounded bg-zinc-950 p-3">
            <div className="text-[9px] font-mono tracking-widest text-zinc-500 mb-2">05 · MULTI-HORIZON EV</div>
            <table className="w-full text-[10px] font-mono">
              <thead>
                <tr className="text-zinc-500 border-b border-zinc-800">
                  <th className="text-left py-1">H</th><th className="text-right">E[ret]</th>
                  <th className="text-right">P(W)</th><th className="text-right">P5</th>
                  <th className="text-right">P95</th><th className="text-right">½K</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-900">
                {analysis.evByH.map((h, i) => (
                  <tr key={i}>
                    <td className="py-1 font-bold">{h.label}</td>
                    <td className={`text-right ${h.ev?.expectedRet > 0 ? 'text-emerald-400' : 'text-rose-400'}`}>{fmtSigned(h.ev?.expectedRet)}</td>
                    <td className="text-right">{fmtPct(h.ev?.pProfit, 0)}</td>
                    <td className="text-right text-rose-300">{fmtSigned(h.ev?.p5Ret)}</td>
                    <td className="text-right text-emerald-300">{fmtSigned(h.ev?.p95Ret)}</td>
                    <td className="text-right text-amber-300">{fmtPct(h.ev?.kellyHalf)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="border border-zinc-800 rounded bg-zinc-950 p-3">
            <div className="text-[9px] font-mono tracking-widest text-zinc-500 mb-2">06 · QUANT DIAGNOSTICS</div>
            <div className="grid grid-cols-2 gap-1.5">
              <Stat label="z (μ₃₀)" value={analysis.z30.toFixed(2)} sub={analysis.z30 < -1 ? 'oversold' : analysis.z30 > 1 ? 'overbought' : 'neutral'}
                accent={analysis.z30 < -1 ? 'text-emerald-300' : analysis.z30 > 1 ? 'text-rose-300' : ''} />
              <Stat label="7d momentum" value={fmtSigned(analysis.mom7)} accent={analysis.mom7 > 0 ? 'text-emerald-300' : 'text-rose-300'} />
              <Stat label="OLS drift" value={analysis.reg ? fmtSigned(analysis.reg.slope, 3) : '—'} sub={analysis.reg ? `R²=${analysis.reg.r2.toFixed(2)} HAC p=${analysis.reg.p.toFixed(3)}` : ''}
                accent={analysis.reg?.p < 0.05 ? (analysis.reg.slope > 0 ? 'text-emerald-400' : 'text-rose-400') : ''} />
              <Stat label="Vol (ann.)" value={fmtPct(analysis.volAnn)} />
              <Stat label="Hurst H" value={analysis.hurst != null ? analysis.hurst.toFixed(2) : '—'}
                sub={analysis.hurst == null ? '' : analysis.hurst > 0.55 ? 'trending' : analysis.hurst < 0.45 ? 'mean-rev' : 'random walk'} />
              <Stat label="N · step" value={`${parsed.history.length} · ${analysis.stepHours.toFixed(1)}h`} />
            </div>
          </section>

          {analysis.wfcv && (
            <section className="border border-zinc-800 rounded bg-zinc-950 p-3">
              <div className="text-[9px] font-mono tracking-widest text-zinc-500 mb-2">07 · WALK-FORWARD CV + ISOTONIC</div>
              <div className="grid grid-cols-2 gap-1.5 mb-2">
                <Stat label="N folds" value={analysis.wfcv.n} />
                <Stat label="Hit rate" value={fmtPct(analysis.wfcv.hit, 0)} />
                <Stat label="Brier raw" value={analysis.wfcv.brier.toFixed(3)}
                  sub={analysis.wfcv.brierCI ? `90% CI [${analysis.wfcv.brierCI[0].toFixed(3)}, ${analysis.wfcv.brierCI[1].toFixed(3)}]` : '↓better; 0.25=coin'}
                  accent={analysis.wfcv.brier < 0.20 ? 'text-emerald-400' : analysis.wfcv.brier > 0.27 ? 'text-rose-400' : ''} />
                <Stat label="IC" value={analysis.wfcv.ic.toFixed(3)}
                  sub={analysis.wfcv.icCI ? `90% CI [${analysis.wfcv.icCI[0].toFixed(3)}, ${analysis.wfcv.icCI[1].toFixed(3)}]` : 'signal↔realized'}
                  accent={analysis.wfcv.ic > 0.05 ? 'text-emerald-300' : analysis.wfcv.ic < -0.05 ? 'text-rose-300' : ''} />
              </div>
              {analysis.calib && (
                <>
                  <div className="grid grid-cols-2 gap-1.5 mb-2">
                    <Stat label="Brier pre→post" value={
                      <span>
                        <span className={analysis.calib.brierPre < 0.25 ? 'text-emerald-400' : 'text-rose-400'}>{analysis.calib.brierPre.toFixed(3)}</span>
                        <span className="text-zinc-500"> → </span>
                        <span className={analysis.calib.brierPost < 0.25 ? 'text-emerald-400' : 'text-rose-400'}>{analysis.calib.brierPost.toFixed(3)}</span>
                      </span>
                    } sub={analysis.calib.improved ? '✓ helped' : '✗ no improvement'} />
                    <Stat label="Verdict" value={
                      analysis.calib.improved && analysis.wfcv.ic > 0
                        ? <span className="text-emerald-400">SIGNAL</span>
                        : analysis.wfcv.ic > 0
                          ? <span className="text-amber-300">SOME</span>
                          : <span className="text-rose-400">NO EDGE</span>
                    } />
                  </div>
                  <canvas ref={reliabilityRef} style={{ width: '100%', display: 'block' }} />
                  <div className="text-[9px] font-mono text-zinc-500 mt-1">
                    <span className="text-sky-400">●</span> raw &nbsp; <span className="text-emerald-400">●</span> post-isotonic. Closer to y=x = better calibrated.
                  </div>
                </>
              )}
            </section>
          )}

          <section className="border border-zinc-800 rounded bg-zinc-950 p-3">
            <div className="text-[9px] font-mono tracking-widest text-zinc-500 mb-2">08 · PRE-COMMIT CHECKLIST</div>
            <div className="text-[10px] font-mono text-zinc-300 space-y-1.5">
              <div className="flex gap-2"><span className="text-emerald-400">▸</span><a href={`https://showzone.gg/cards?q=${encodeURIComponent(parsed.name)}`} target="_blank" rel="noopener noreferrer" className="text-emerald-300 hover:text-emerald-400 underline-offset-2 hover:underline">ShowZone trend</a> — verify 7d direction</div>
              <div className="flex gap-2"><span className="text-emerald-400">▸</span><a href={`https://www.showdd.io/players?q=${encodeURIComponent(parsed.name)}`} target="_blank" rel="noopener noreferrer" className="text-emerald-300 hover:text-emerald-400 underline-offset-2 hover:underline">showdd.io</a> — past update history</div>
              <div className="flex gap-2"><span className="text-emerald-400">▸</span><a href={`https://www.reddit.com/r/MLBTheShow/search/?q=${encodeURIComponent(parsed.name)}&restrict_sr=1`} target="_blank" rel="noopener noreferrer" className="text-emerald-300 hover:text-emerald-400 underline-offset-2 hover:underline">r/MLBTheShow</a> — community sentiment</div>
              <div className="flex gap-2"><span className="text-emerald-400">▸</span><a href={`https://www.baseball-reference.com/search/search.fcgi?search=${encodeURIComponent(parsed.name)}`} target="_blank" rel="noopener noreferrer" className="text-emerald-300 hover:text-emerald-400 underline-offset-2 hover:underline">Baseball-Reference</a> — recent real-MLB stats</div>
            </div>
          </section>
        </>
      )}
    </div>
  );
}

function OvrTab() {  // augmented
  const [name, setName] = useState('');
  const [ovr, setOvr] = useState('');
  const [price, setPrice] = useState('');
  const [rarity, setRarity] = useState('Diamond');
  const [position, setPosition] = useState('hitter');

  // Hitter inputs
  const [recentOPS, setRecentOPS] = useState('');
  const [seasonOPS, setSeasonOPS] = useState('');
  const [recentBA, setRecentBA] = useState('');
  const [seasonBA, setSeasonBA] = useState('');
  // Pitcher inputs
  const [recentERA, setRecentERA] = useState('');
  const [seasonERA, setSeasonERA] = useState('');
  const [recentWHIP, setRecentWHIP] = useState('');
  const [seasonWHIP, setSeasonWHIP] = useState('');

  const calc = useMemo(() => {
    const n = (s) => { const v = parseFloat(s); return isNaN(v) ? null : v; };
    let z = null, signals = [];
    if (position === 'hitter') {
      const rO = n(recentOPS), sO = n(seasonOPS), rB = n(recentBA), sB = n(seasonBA);
      const zs = [];
      // OPS: typical season std ~0.080 OPS; recent (14d) is noisier so use 0.110
      if (rO != null && sO != null) {
        const dz = (rO - sO) / 0.110;
        zs.push(dz);
        signals.push({ label: 'OPS Δ', value: rO - sO, z: dz });
      }
      // BA: typical 14d std ~0.045
      if (rB != null && sB != null) {
        const dz = (rB - sB) / 0.045;
        zs.push(dz);
        signals.push({ label: 'BA Δ', value: rB - sB, z: dz });
      }
      if (zs.length) z = mean(zs);
    } else {
      const rE = n(recentERA), sE = n(seasonERA), rW = n(recentWHIP), sW = n(seasonWHIP);
      const zs = [];
      // ERA std ~1.20 (lower = better, so flip sign)
      if (rE != null && sE != null) {
        const dz = -(rE - sE) / 1.20;
        zs.push(dz);
        signals.push({ label: 'ERA Δ', value: rE - sE, z: dz });
      }
      // WHIP std ~0.20
      if (rW != null && sW != null) {
        const dz = -(rW - sW) / 0.20;
        zs.push(dz);
        signals.push({ label: 'WHIP Δ', value: rW - sW, z: dz });
      }
      if (zs.length) z = mean(zs);
    }
    // Map z to ΔOVR
    let dOvr = 0;
    if (z != null) {
      if (z > 2) dOvr = 3;
      else if (z > 1.2) dOvr = 2;
      else if (z > 0.5) dOvr = 1;
      else if (z < -2) dOvr = -3;
      else if (z < -1.2) dOvr = -2;
      else if (z < -0.5) dOvr = -1;
    }
    // Map ΔOVR to ΔPrice% by rarity band
    let pricePct = 0, boundaryRisk = 'low';
    const ovrN = parseInt(ovr) || 0;
    if (rarity === 'Diamond' && dOvr !== 0) {
      pricePct = dOvr * 0.15;  // ~15%/OVR within Diamond
    } else if (rarity === 'Gold' && dOvr !== 0) {
      pricePct = dOvr * 0.20;
      // Gold→Diamond boundary at OVR 85
      if (ovrN >= 84 && ovrN + dOvr >= 85) {
        pricePct = Math.max(pricePct, 1.50);  // 100-300% boundary jump, conservative ~150%
        boundaryRisk = 'high';
      }
    } else if (rarity === 'Silver' && dOvr !== 0) {
      pricePct = dOvr * 0.10;
      if (ovrN >= 79 && ovrN + dOvr >= 80) {
        pricePct = Math.max(pricePct, 0.80);
        boundaryRisk = 'high';
      }
    } else if (rarity === 'Bronze' && dOvr !== 0) {
      pricePct = dOvr * 0.05;
      if (ovrN >= 74 && ovrN + dOvr >= 75) {
        pricePct = Math.max(pricePct, 0.50);
        boundaryRisk = 'medium';
      }
    }
    return { z, dOvr, pricePct, boundaryRisk, signals };
  }, [position, recentOPS, seasonOPS, recentBA, seasonBA, recentERA, seasonERA, recentWHIP, seasonWHIP, rarity, ovr]);

  const ready = name.trim() && ovr && (
    (position === 'hitter' && (recentOPS || recentBA)) ||
    (position === 'pitcher' && (recentERA || recentWHIP))
  );

  return (
    <div className="space-y-3">
      <RosterUpdateBanner />
      <section className="border border-zinc-800 rounded bg-zinc-950 p-3">
        <div className="text-[9px] font-mono tracking-widest text-zinc-500 mb-2">01 · MANUAL OVR DELTA CALCULATOR</div>
        <div className="text-[10px] font-mono text-zinc-400 mb-2">Enter recent + season stats. Computes weighted z-score → ΔOVR → ΔPrice by rarity band.</div>
        <div className="text-[9px] font-mono text-zinc-500 mb-2">Pull stats from <span className="text-emerald-400">baseball-reference.com</span> or <span className="text-emerald-400">fangraphs.com</span> · last 14 days vs season.</div>

        <input value={name} onChange={e => setName(e.target.value)} placeholder="player name (any caps)"
          className="w-full bg-black border border-zinc-800 px-2 py-2 text-xs font-mono text-zinc-200 rounded mb-2 focus:border-emerald-700 outline-none" />

        <div className="grid grid-cols-3 gap-2 mb-2">
          <select value={rarity} onChange={e => setRarity(e.target.value)} className="bg-black border border-zinc-800 px-2 py-2 text-xs font-mono text-zinc-200 rounded">
            <option>Diamond</option><option>Gold</option><option>Silver</option><option>Bronze</option>
          </select>
          <input value={ovr} onChange={e => setOvr(e.target.value)} placeholder="OVR" type="number"
            className="bg-black border border-zinc-800 px-2 py-2 text-xs font-mono text-zinc-200 rounded focus:border-emerald-700 outline-none" />
          <input value={price} onChange={e => setPrice(e.target.value)} placeholder="price (opt)" type="number"
            className="bg-black border border-zinc-800 px-2 py-2 text-xs font-mono text-zinc-200 rounded focus:border-emerald-700 outline-none" />
        </div>

        <div className="flex gap-2 mb-2">
          <button onClick={() => setPosition('hitter')} className={`flex-1 px-2 py-1.5 text-[10px] font-mono rounded ${position === 'hitter' ? 'bg-emerald-600 text-black font-bold' : 'bg-zinc-900 text-zinc-400 border border-zinc-700'}`}>HITTER</button>
          <button onClick={() => setPosition('pitcher')} className={`flex-1 px-2 py-1.5 text-[10px] font-mono rounded ${position === 'pitcher' ? 'bg-emerald-600 text-black font-bold' : 'bg-zinc-900 text-zinc-400 border border-zinc-700'}`}>PITCHER</button>
        </div>

        {position === 'hitter' ? (
          <div className="grid grid-cols-2 gap-2">
            <div><div className="text-[9px] font-mono text-zinc-500 uppercase tracking-widest mb-1">Recent OPS (14d)</div>
              <input value={recentOPS} onChange={e => setRecentOPS(e.target.value)} type="number" step="0.001" placeholder="0.950"
                className="w-full bg-black border border-zinc-800 px-2 py-2 text-xs font-mono text-zinc-200 rounded" /></div>
            <div><div className="text-[9px] font-mono text-zinc-500 uppercase tracking-widest mb-1">Season OPS</div>
              <input value={seasonOPS} onChange={e => setSeasonOPS(e.target.value)} type="number" step="0.001" placeholder="0.820"
                className="w-full bg-black border border-zinc-800 px-2 py-2 text-xs font-mono text-zinc-200 rounded" /></div>
            <div><div className="text-[9px] font-mono text-zinc-500 uppercase tracking-widest mb-1">Recent BA (14d)</div>
              <input value={recentBA} onChange={e => setRecentBA(e.target.value)} type="number" step="0.001" placeholder="0.310"
                className="w-full bg-black border border-zinc-800 px-2 py-2 text-xs font-mono text-zinc-200 rounded" /></div>
            <div><div className="text-[9px] font-mono text-zinc-500 uppercase tracking-widest mb-1">Season BA</div>
              <input value={seasonBA} onChange={e => setSeasonBA(e.target.value)} type="number" step="0.001" placeholder="0.275"
                className="w-full bg-black border border-zinc-800 px-2 py-2 text-xs font-mono text-zinc-200 rounded" /></div>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-2">
            <div><div className="text-[9px] font-mono text-zinc-500 uppercase tracking-widest mb-1">Recent ERA (14d)</div>
              <input value={recentERA} onChange={e => setRecentERA(e.target.value)} type="number" step="0.01" placeholder="2.50"
                className="w-full bg-black border border-zinc-800 px-2 py-2 text-xs font-mono text-zinc-200 rounded" /></div>
            <div><div className="text-[9px] font-mono text-zinc-500 uppercase tracking-widest mb-1">Season ERA</div>
              <input value={seasonERA} onChange={e => setSeasonERA(e.target.value)} type="number" step="0.01" placeholder="3.40"
                className="w-full bg-black border border-zinc-800 px-2 py-2 text-xs font-mono text-zinc-200 rounded" /></div>
            <div><div className="text-[9px] font-mono text-zinc-500 uppercase tracking-widest mb-1">Recent WHIP</div>
              <input value={recentWHIP} onChange={e => setRecentWHIP(e.target.value)} type="number" step="0.01" placeholder="0.95"
                className="w-full bg-black border border-zinc-800 px-2 py-2 text-xs font-mono text-zinc-200 rounded" /></div>
            <div><div className="text-[9px] font-mono text-zinc-500 uppercase tracking-widest mb-1">Season WHIP</div>
              <input value={seasonWHIP} onChange={e => setSeasonWHIP(e.target.value)} type="number" step="0.01" placeholder="1.20"
                className="w-full bg-black border border-zinc-800 px-2 py-2 text-xs font-mono text-zinc-200 rounded" /></div>
          </div>
        )}
      </section>

      {ready && (
        <section className="border border-zinc-800 rounded bg-zinc-950 p-3 space-y-2">
          <div className="text-[9px] font-mono tracking-widest text-zinc-500">02 · PREDICTION</div>
          <div className="grid grid-cols-2 gap-1.5">
            <Stat label="ΔOVR predicted" value={(calc.dOvr >= 0 ? '+' : '') + calc.dOvr}
              accent={calc.dOvr > 0 ? 'text-emerald-400' : calc.dOvr < 0 ? 'text-rose-400' : ''}
              sub={`from weighted z=${calc.z != null ? calc.z.toFixed(2) : '—'}`} />
            <Stat label="ΔPrice est" value={calc.pricePct !== 0 ? fmtSigned(calc.pricePct) : '—'}
              accent={calc.pricePct > 0 ? 'text-emerald-400' : calc.pricePct < 0 ? 'text-rose-400' : ''}
              sub={`rarity band: ${rarity}`} />
          </div>
          <div>
            {calc.boundaryRisk !== 'low' && <Pill tone={calc.boundaryRisk === 'high' ? 'warn' : 'neutral'}>boundary: {calc.boundaryRisk}</Pill>}
            <Pill tone={Math.abs(calc.z || 0) > 1.5 ? 'info' : 'neutral'}>conf: {Math.abs(calc.z || 0) > 1.5 ? 'high' : Math.abs(calc.z || 0) > 0.8 ? 'medium' : 'low'}</Pill>
            <Pill>{position}</Pill>
          </div>
          {calc.signals.length > 0 && (
            <div className="border-t border-zinc-800 pt-2">
              <div className="text-[9px] font-mono uppercase tracking-widest text-zinc-500 mb-1">SIGNAL DETAIL</div>
              {calc.signals.map((s, i) => (
                <div key={i} className="flex justify-between text-[10px] font-mono">
                  <span className="text-zinc-400">{s.label}</span>
                  <span className={s.z > 0 ? 'text-emerald-400' : 'text-rose-400'}>
                    {s.value >= 0 ? '+' : ''}{s.value.toFixed(3)} (z={s.z >= 0 ? '+' : ''}{s.z.toFixed(2)})
                  </span>
                </div>
              ))}
            </div>
          )}
          {price && calc.pricePct !== 0 && (
            <div className="border-t border-zinc-800 pt-2">
              <div className="text-[9px] font-mono uppercase tracking-widest text-zinc-500">EXPECTED POST-UPDATE</div>
              <div className="text-base font-mono font-bold">{stubs(Number(price) * (1 + calc.pricePct))}</div>
              <div className="text-[9px] text-zinc-500 font-mono">from {stubs(Number(price))}</div>
            </div>
          )}
        </section>
      )}
    </div>
  );
}

function ValidateTab() {
  const [trials, setTrials] = useState(8);
  const [n, setN] = useState(200);
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState({ tag: '', t: 0, total: 0 });
  const [results, setResults] = useState(null);

  const mulberry32 = seed => { let a = seed | 0; return () => { a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; };
  const gauss = rng => { const u1 = Math.max(rng(), 1e-9), u2 = rng(); return Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2); };

  const REGIMES = {
    GBM: { color: '#94a3b8', desc: 'random walk', gen: (n, s) => { const r = mulberry32(s); const o = [10000]; for (let i = 1; i < n; i++) o.push(o[i - 1] * Math.exp(0.001 + gauss(r) * 0.012)); return o; } },
    AR1: { color: '#a78bfa', desc: 'momentum φ=0.6', gen: (n, s) => { const r = mulberry32(s); const rets = [gauss(r) * 0.012]; for (let i = 1; i < n; i++) rets.push(0.6 * rets[i - 1] + gauss(r) * 0.012); const o = [10000]; for (let i = 1; i < n; i++) o.push(o[i - 1] * Math.exp(rets[i])); return o; } },
    REGIME: { color: '#fb923c', desc: 'bull/bear/flat', gen: (n, s) => { const r = mulberry32(s); const m = []; for (let i = 0; i < Math.ceil(n / 50); i++) { const rr = r(); const mu = rr < 0.33 ? 0.003 : rr < 0.66 ? -0.003 : 0; for (let j = 0; j < 50; j++) m.push(mu); } const o = [10000]; for (let i = 1; i < n; i++) o.push(o[i - 1] * Math.exp(m[i] + gauss(r) * 0.012)); return o; } },
    JUMP: { color: '#f43f5e', desc: 'jump-diffusion', gen: (n, s) => { const r = mulberry32(s); const o = [10000]; for (let i = 1; i < n; i++) { const b = gauss(r) * 0.010; const j = r() < 0.02 ? (r() < 0.5 ? -0.08 : 0.08) : 0; o.push(o[i - 1] * Math.exp(b + j)); } return o; } },
    MEANREV: { color: '#38bdf8', desc: 'mean-rev OU', gen: (n, s) => { const r = mulberry32(s); const mu = Math.log(10000); const lp = [mu]; for (let i = 1; i < n; i++) lp.push(lp[i - 1] + (-0.05 * (lp[i - 1] - mu)) + gauss(r) * 0.012); return lp.map(Math.exp); } },
  };

  const run = async () => {
    setRunning(true); setResults(null);
    const out = {}; const tags = Object.keys(REGIMES); let done = 0; const total = trials * tags.length;
    for (const tag of tags) {
      const tm = [];
      for (let t = 0; t < trials; t++) {
        setProgress({ tag, t: t + 1, total: trials });
        await new Promise(r => setTimeout(r, 0));
        const prices = REGIMES[tag].gen(n, t * 17 + tag.charCodeAt(0));
        const wf = walkForwardCV(prices, 20, 50, 150);
        if (!wf || wf.trades.length < 30) { done++; continue; }
        const half = Math.floor(wf.trades.length / 2);
        const tP = wf.trades.slice(0, half).map(x => x.pUp);
        const tW = wf.trades.slice(0, half).map(x => x.win);
        const map = pavIsotonic(tP, tW);
        const test = wf.trades.slice(half);
        const calP = test.map(x => isotonicApply(map, x.pUp));
        const realW = test.map(x => x.win);
        tm.push({ brierPre: mean(test.map(x => (x.pUp - x.win) ** 2)), brierPost: mean(calP.map((p, i) => (p - realW[i]) ** 2)), ic: wf.ic, hit: wf.hit });
        done++;
      }
      if (tm.length) {
        const ms = key => ({ mean: mean(tm.map(x => x[key])), std: std(tm.map(x => x[key])) });
        out[tag] = { color: REGIMES[tag].color, desc: REGIMES[tag].desc, n: tm.length, brierPre: ms('brierPre'), brierPost: ms('brierPost'), ic: ms('ic'), hit: ms('hit'), preAll: tm.map(x => x.brierPre), postAll: tm.map(x => x.brierPost) };
      }
    }
    setResults(out); setRunning(false);
  };

  const violinRef = useViolinChart(results);
  const allNeg = results && Object.values(results).every(r => r.ic.mean <= 0.05);
  const positives = results ? Object.entries(results).filter(([_, r]) => r.ic.mean > 0.05).map(([t]) => t) : [];

  return (
    <div className="space-y-3">
      <section className="border border-zinc-800 rounded bg-zinc-950 p-3">
        <div className="text-[9px] font-mono tracking-widest text-zinc-500 mb-2">01 · MONTE CARLO VALIDATION</div>
        <div className="text-[10px] font-mono text-zinc-400 mb-2">Stress-test bootstrap forecaster vs 5 synthetic regimes. <span className="text-amber-300">Reveals signal vs noise honestly.</span></div>
        <div className="grid grid-cols-2 gap-2 mb-2">
          <div>
            <div className="text-[9px] font-mono text-zinc-500 uppercase tracking-widest mb-1">Trials</div>
            <input type="number" value={trials} min={3} max={20} onChange={e => setTrials(Math.max(3, Math.min(20, +e.target.value)))} className="w-full bg-black border border-zinc-800 px-2 py-2 text-xs font-mono text-zinc-200 rounded" />
          </div>
          <div>
            <div className="text-[9px] font-mono text-zinc-500 uppercase tracking-widest mb-1">N prices</div>
            <input type="number" value={n} min={150} max={400} onChange={e => setN(Math.max(150, Math.min(400, +e.target.value)))} className="w-full bg-black border border-zinc-800 px-2 py-2 text-xs font-mono text-zinc-200 rounded" />
          </div>
        </div>
        <button onClick={run} disabled={running} className="w-full px-3 py-2 text-[11px] font-mono font-bold bg-emerald-600 text-black rounded disabled:bg-zinc-800 disabled:text-zinc-600">
          {running ? `${progress.tag} ${progress.t}/${progress.total}` : 'RUN MC'}
        </button>
      </section>
      {results && (
        <>
          <section className="border border-zinc-800 rounded bg-zinc-950 p-3">
            <div className="text-[9px] font-mono tracking-widest text-zinc-500 mb-2">02 · CROSS-REGIME RESULTS</div>
            <table className="w-full text-[10px] font-mono">
              <thead><tr className="text-zinc-500 border-b border-zinc-800"><th className="text-left py-1">REGIME</th><th className="text-right">BRIER pre</th><th className="text-right">post</th><th className="text-right">IC</th><th className="text-right">VERDICT</th></tr></thead>
              <tbody className="divide-y divide-zinc-900">
                {Object.entries(results).map(([tag, r]) => {
                  const v = r.brierPost.mean < 0.25 && r.ic.mean > 0 ? ['SIGNAL', 'bull'] : r.ic.mean > 0 ? ['+IC', 'warn'] : ['NO EDGE', 'bear'];
                  return (
                    <tr key={tag}>
                      <td className="py-1.5"><span style={{ color: r.color }}>{tag}</span><br /><span className="text-[8px] text-zinc-500">{r.desc}</span></td>
                      <td className={`text-right ${r.brierPre.mean < 0.25 ? 'text-emerald-400' : 'text-rose-400'}`}>{r.brierPre.mean.toFixed(3)}</td>
                      <td className={`text-right ${r.brierPost.mean < 0.25 ? 'text-emerald-400' : 'text-rose-400'}`}>{r.brierPost.mean.toFixed(3)}</td>
                      <td className={`text-right ${r.ic.mean > 0 ? 'text-emerald-400' : 'text-rose-400'}`}>{r.ic.mean >= 0 ? '+' : ''}{r.ic.mean.toFixed(3)}</td>
                      <td className="text-right"><Pill tone={v[1]}>{v[0]}</Pill></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </section>
          <section className="border border-zinc-800 rounded bg-zinc-950 p-3">
            <div className="text-[9px] font-mono tracking-widest text-zinc-500 mb-2">03 · BRIER DISTRIBUTION</div>
            <canvas ref={violinRef} style={{ width: '100%', display: 'block' }} />
            <div className="text-[9px] font-mono text-zinc-500 mt-1">Each dot = one trial. <span className="text-sky-400">●</span> raw <span className="text-emerald-400">●</span> post-cal. Dashed = 0.25 baseline.</div>
          </section>
          <section className="border border-zinc-800 rounded bg-zinc-950 p-3">
            <div className="text-[9px] font-mono tracking-widest text-zinc-500 mb-2">04 · HONEST ASSESSMENT</div>
            {allNeg ? (
              <div className="text-[10px] font-mono border-l-2 border-rose-500 pl-2 text-rose-300 mb-2">
                <strong>No regime shows IC&gt;0.05.</strong> Bootstrap doesn't add directional signal at this horizon. Trust EV cone for variance, not central tendency.
              </div>
            ) : (
              <div className="text-[10px] font-mono border-l-2 border-emerald-500 pl-2 text-emerald-300 mb-2">
                <strong>Positive IC in:</strong> {positives.join(', ')}. Model has edge here.
              </div>
            )}
            <div className="text-[10px] font-mono border-l-2 border-amber-500 pl-2 text-amber-300">
              Treat probability outputs as scenario expectations, not calibrated truth. Trust z-scores, Hurst, Kelly more than P(profit).
            </div>
          </section>
        </>
      )}
    </div>
  );
}

function MethodTab() {
  return (
    <div className="space-y-3">
      <section className="border border-zinc-800 rounded bg-zinc-950 p-3">
        <div className="text-[9px] font-mono tracking-widest text-zinc-500 mb-2">01 · ARCHITECTURE</div>
        <div className="text-[10px] font-mono text-zinc-300 space-y-1.5">
          <div><span className="text-emerald-400">Forecast:</span> Block bootstrap (Politis-Romano 1994), L=⌊N^0.4⌋.</div>
          <div><span className="text-emerald-400">EV:</span> Pay ask, exit at forecast×(bid/ask)×0.90.</div>
          <div><span className="text-emerald-400">Drift:</span> OLS log-price ~ t with empirical-Bayes shrinkage.</div>
          <div><span className="text-emerald-400">Regime:</span> Hurst R/S + variance-ratio at k=2,4.</div>
          <div><span className="text-emerald-400">Validation:</span> Walk-forward CV with Brier/log-loss/IC.</div>
          <div><span className="text-emerald-400">Calibration:</span> PAV isotonic regression.</div>
        </div>
      </section>
      <section className="border border-zinc-800 rounded bg-zinc-950 p-3">
        <div className="text-[9px] font-mono tracking-widest text-zinc-500 mb-2">02 · LIMITATIONS</div>
        <div className="text-[10px] font-mono text-zinc-300 space-y-1.5">
          <div className="border-l-2 border-rose-500 pl-2 text-rose-300">Bootstrap had near-zero/negative IC across synthetic regimes. Recent drift doesn't reliably predict near-future direction.</div>
          <div className="border-l-2 border-amber-500 pl-2 text-amber-300">Treat probability outputs as scenario expectations. Variance estimates (cone width) are well-calibrated; central tendency isn't.</div>
          <div className="border-l-2 border-emerald-500 pl-2 text-emerald-300">Reliable: z-score extremes, Hurst regime detection, post-tax breakeven, Kelly sizing.</div>
        </div>
      </section>
      <section className="border border-zinc-800 rounded bg-zinc-950 p-3">
        <div className="text-[9px] font-mono tracking-widest text-zinc-500 mb-2">03 · WORKFLOW</div>
        <div className="text-[10px] font-mono text-zinc-300 space-y-1">
          <div>1. CARD → search by name → tap result → tap OPEN JSON → copy → paste → PARSE.</div>
          <div>2. OVR PRED → enter Live Series player → predict ΔOVR.</div>
          <div>3. VALIDATE → run MC stress test in-browser.</div>
        </div>
      </section>
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState('card');
  const tabs = [['card', 'CARD'], ['ovr', 'OVR'], ['validate', 'VALIDATE'], ['method', 'METHOD']];
  return (
    <div className="min-h-screen bg-black text-zinc-100" style={{ fontFamily: 'ui-monospace, monospace' }}>
      <div className="border-b border-zinc-800 bg-gradient-to-b from-zinc-950 to-black sticky top-0 z-20">
        <div className="px-3 py-2 flex items-center justify-between">
          <div>
            <div className="text-[9px] tracking-[0.3em] text-emerald-400">DD//TERMINAL</div>
            <div className="text-sm font-bold tracking-tight">MLB THE SHOW 26 — INVESTMENT ENGINE</div>
          </div>
          <div className="text-right text-[9px] text-zinc-500">v3.3 · iPhone</div>
        </div>
        <div className="flex border-t border-zinc-900 overflow-x-auto">
          {tabs.map(([k, l]) => (
            <button key={k} onClick={() => setTab(k)}
              className={`px-3 py-2 text-[10px] tracking-wider whitespace-nowrap border-r border-zinc-900 ${tab === k ? 'bg-zinc-900 text-emerald-400 border-b-2 border-b-emerald-500' : 'text-zinc-500'}`}>{l}</button>
          ))}
        </div>
      </div>
      <div className="px-3 py-3 max-w-3xl mx-auto">
        {tab === 'card' && <CardTab />}
        {tab === 'ovr' && <OvrTab />}
        {tab === 'validate' && <ValidateTab />}
        {tab === 'method' && <MethodTab />}
        <div className="text-center text-[9px] text-zinc-700 py-4">v3.3 · independent of San Diego Studio</div>
      </div>
    </div>
  );
}
