'use client';
import { FormEvent, useEffect, useState } from 'react';

type Locale = 'ru' | 'kz' | 'en';
type FaceitPlayer = { player_id: string; nickname: string; avatar?: string; country?: string; games?: Record<string, { skill_level?: number; faceit_elo?: number }> };
const API = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const copy = {
 ru: { eyebrow:'COUNTER-STRIKE 2 · MATCH INTELLIGENCE', title:'Твои матчи. Твои демки. Твой анализ.', subtitle:'Единый центр матчей Steam и FACEIT: загрузка демок, разбор раундов и статистика игроков.', steam:'Войти через Steam', faceitLogin:'Войти через FACEIT', faceit:'Найти игрока FACEIT', matches:'Матчи', demos:'Демки', analytics:'Аналитика', replay:'2D Replay', highlights:'Хайлайты', recent:'Последние матчи', empty:'Матчи появятся после подключения источника. Мы не показываем вымышленные матчи или ссылки.', status:'Проверка подключения API…', soon:'Реальные данные · Без вымышленных матчей', nickname:'Никнейм FACEIT', search:'Поиск', loading:'Ищем…', notConfigured:'FACEIT API пока не настроен на сервере. Добавьте FACEIT_API_KEY в Render.', noPlayers:'Игроки не найдены.', steamConnected:'Steam успешно подключён.', steamWait:'Steam авторизация будет доступна после настройки секретного ключа сервера.' },
 kz: { eyebrow:'COUNTER-STRIKE 2 · MATCH INTELLIGENCE', title:'Матчтарың. Демо-файлдарың. Талдауың.', subtitle:'Steam және FACEIT матчтары: демо жүктеу, раундтарды талдау және ойыншы статистикасы.', steam:'Steam арқылы кіру', faceitLogin:'FACEIT арқылы кіру', faceit:'FACEIT ойыншысын іздеу', matches:'Матчтар', demos:'Демолар', analytics:'Талдау', replay:'2D Replay', highlights:'Үздік сәттер', recent:'Соңғы матчтар', empty:'Дереккөз қосылғаннан кейін матчтар осында көрінеді. Жалған матчтар көрсетілмейді.', status:'API байланысы тексерілуде…', soon:'Нақты деректер · Жалған матчтарсыз', nickname:'FACEIT никнеймі', search:'Іздеу', loading:'Іздеу…', notConfigured:'FACEIT API серверде бапталмаған. Render-ге FACEIT_API_KEY қосыңыз.', noPlayers:'Ойыншылар табылмады.', steamConnected:'Steam сәтті қосылды.', steamWait:'Steam кіру сервер құпия кілті бапталғаннан кейін қолжетімді болады.' },
 en: { eyebrow:'COUNTER-STRIKE 2 · MATCH INTELLIGENCE', title:'Your matches. Your demos. Your analysis.', subtitle:'One hub for Steam and FACEIT matches: demo downloads, round review and player analytics.', steam:'Sign in with Steam', faceitLogin:'Sign in with FACEIT', faceit:'Find FACEIT player', matches:'Matches', demos:'Demos', analytics:'Analytics', replay:'2D Replay', highlights:'Highlights', recent:'Recent matches', empty:'Matches appear here after a provider is connected. No fake matches or links.', status:'Checking API connection…', soon:'Live data · No fabricated matches', nickname:'FACEIT nickname', search:'Search', loading:'Searching…', notConfigured:'FACEIT API is not configured on the server. Add FACEIT_API_KEY in Render.', noPlayers:'No players found.', steamConnected:'Steam connected successfully.', steamWait:'Steam sign-in becomes available after the server secret is configured.' }
};
export default function Home() {
 const [locale,setLocale] = useState<Locale>('ru');
 const [nickname,setNickname] = useState('');
 const [players,setPlayers] = useState<FaceitPlayer[]>([]);
 const [error,setError] = useState('');
 const [busy,setBusy] = useState(false);
 const [apiStatus,setApiStatus] = useState('checking');
 const [steamId,setSteamId] = useState<string|null>(null);
 const [faceitUser,setFaceitUser] = useState<{nickname?:string;sub?:string;picture?:string}|null>(null);
 const t = copy[locale];
 useEffect(() => {
   fetch(API + '/api/v1/status').then(async r => { if(!r.ok) throw new Error(); const d=await r.json(); setApiStatus(d.integrations?.faceit_data_api || 'online'); })
     .catch(() => setApiStatus('offline'));
   fetch(API + '/api/v1/auth/me',{credentials:'include'}).then(r=>r.json()).then(d=>{if(d.authenticated)setSteamId(d.steam_id)}).catch(()=>{});
   fetch(API + '/api/v1/auth/faceit/me',{credentials:'include'}).then(r=>r.json()).then(d=>{if(d.authenticated)setFaceitUser(d.user)}).catch(()=>{});
 }, []);
 async function searchFaceit(e:FormEvent) {
   e.preventDefault(); if(nickname.trim().length<2)return;
   setBusy(true); setError(''); setPlayers([]);
   try {
     const r=await fetch(API+'/api/v1/faceit/players?nickname='+encodeURIComponent(nickname.trim()));
     const data=await r.json();
     if(!r.ok) throw new Error(data.detail || t.notConfigured);
     setPlayers(data.items || []);
     if(!(data.items||[]).length)setError(t.noPlayers);
   } catch(err) { setError(err instanceof Error ? err.message : t.notConfigured); }
   finally { setBusy(false); }
 }
 const steamLogin = () => { window.location.href=API+'/api/v1/auth/steam/login'; };
 const faceitLogin = () => { window.location.href=API+'/api/v1/auth/faceit/login'; };
 return <main className="shell"><header className="topbar"><a className="brand" href="#"><span className="brand-mark">D</span><span>CS2 <b>DEMO HUB</b></span></a><nav><a href="#matches">{t.matches}</a><a href="#analytics">{t.analytics}</a><a href="#replay">{t.replay}</a></nav><div className="locale">{(['ru','kz','en'] as Locale[]).map(x=><button key={x} className={locale===x?'active':''} onClick={()=>setLocale(x)}>{x.toUpperCase()}</button>)}</div></header>
 <section className="hero"><div className="hero-copy"><div className="eyebrow"><span className="pulse"/>{t.eyebrow}</div><h1>{t.title}</h1><p>{t.subtitle}</p><div className="actions"><button className="primary" onClick={faceitLogin}>{faceitUser ? 'FACEIT · '+(faceitUser.nickname||faceitUser.sub||'connected') : t.faceitLogin} ↗</button><button className="secondary" onClick={steamLogin}>{steamId ? 'Steam · '+steamId : t.steam} ↗</button><a className="secondary button-link" href="#faceit">{t.faceit} ↗</a></div><div className="fine">{faceitUser ? 'FACEIT account connected · '+(faceitUser.nickname||faceitUser.sub||'') : (steamId ? t.steamConnected : t.status+' '+apiStatus)}</div></div><div className="hero-art"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="crosshair">✛</div><div className="art-label">DEMO<br/><strong>INTELLIGENCE</strong></div><div className="art-bottom">STEAM <i>×</i> FACEIT <i>×</i> CS2</div></div></section>
 <section className="stats" id="analytics">{[[t.matches,'—','MATCH DATABASE'],[t.demos,'—','DEMO STORAGE'],[t.analytics,'—','PLAYER METRICS'],[t.highlights,'—','VIDEO EXPORT']].map(([label,value,sub])=><article className="stat" key={sub}><span>{sub}</span><strong>{value}</strong><small>{label}</small></article>)}</section>
 <section className="content-grid" id="matches"><article className="panel recent"><div className="panel-head"><div><span className="eyebrow">MATCH CENTER</span><h2>{t.recent}</h2></div><span className="tag">LIVE DATA ONLY</span></div><div className="empty"><div className="empty-icon">⌁</div><p>{t.empty}</p></div></article><article className="panel modules" id="replay"><span className="eyebrow">YOUR WORKSPACE</span><h2>Modules</h2>{[t.demos,t.analytics,t.replay,t.highlights].map((x,i)=><div className="module-row" key={x}><span className="module-number">0{i+1}</span><b>{x}</b><span className="module-state">{i===0?'API INTEGRATION':'PLANNED'}</span></div>)}</article></section>
 <section className="panel faceit-panel" id="faceit"><div className="panel-head"><div><span className="eyebrow">FACEIT DATA API</span><h2>{t.faceit}</h2></div><span className="tag">{apiStatus==='configured'?'CONNECTED':'SETUP REQUIRED'}</span></div><form className="faceit-search" onSubmit={searchFaceit}><input value={nickname} onChange={e=>setNickname(e.target.value)} placeholder={t.nickname} minLength={2} maxLength={32}/><button className="primary" disabled={busy||nickname.trim().length<2}>{busy?t.loading:t.search}</button></form>{error&&<p className="error-message">{error}</p>}{players.length>0&&<div className="players-list">{players.map(p=><article className="player-card" key={p.player_id}><div className="player-avatar">{p.avatar?<img src={p.avatar} alt=""/>:<span>{p.nickname?.slice(0,1)?.toUpperCase()}</span>}</div><div><b>{p.nickname}</b><small>{p.country||'—'} · {p.games?.cs2?.faceit_elo ? p.games.cs2.faceit_elo+' ELO' : 'CS2'}</small></div><a href={API+'/api/v1/faceit/players/'+encodeURIComponent(p.player_id)+'/matches'} target="_blank" rel="noreferrer">Матчи ↗</a></article>)}</div>}</section>
 <footer><span>CS2 DEMO HUB · FOUNDATION 0.2.0</span><span>{t.soon}</span></footer></main>;
}
