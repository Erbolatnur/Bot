'use client';
import { FormEvent, useEffect, useState } from 'react';

type Locale = 'ru' | 'kz' | 'en';
type FaceitPlayer = { player_id: string; nickname: string; avatar?: string; country?: string; games?: Record<string, { skill_level?: number; faceit_elo?: number }> };
type FaceitMatch = { match_id: string; started_at?: number; finished_at?: number; game_mode?: string; map?: string | null; demo_available?: boolean };
type SteamImportResult = { status: string; next_code: string | null; message?: string };
type SteamDecodedMatch = { share_code:string; match_id:string; reservation_id:string; tv_port:number; steam_launch_uri:string; metadata_available:boolean };
const API = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const copy = {
 ru: { eyebrow:'COUNTER-STRIKE 2 · MATCH INTELLIGENCE', title:'Твои матчи. Твои демки. Твой анализ.', subtitle:'Единый центр матчей Steam и FACEIT: загрузка демок, разбор раундов и статистика игроков.', steam:'Войти через Steam', faceitLogin:'Войти через FACEIT', faceit:'Найти игрока FACEIT', matches:'Матчи', demos:'Демки', analytics:'Аналитика', replay:'2D Replay', highlights:'Хайлайты', recent:'Последние матчи', empty:'Матчи появятся после подключения источника. Мы не показываем вымышленные матчи или ссылки.', status:'Проверка подключения API…', soon:'Реальные данные · Без вымышленных матчей', nickname:'Никнейм FACEIT', search:'Поиск', loading:'Ищем…', notConfigured:'FACEIT API пока не настроен на сервере. Добавьте FACEIT_API_KEY в Render.', noPlayers:'Игроки не найдены.', steamConnected:'Steam успешно подключён.', steamWait:'Steam авторизация будет доступна после настройки секретного ключа сервера.', steamImport:'Импорт матчей Steam', steamAuthCode:'Game Authentication Code', steamMatchCode:'Последний Match Sharing Code', steamImportHelp:'Коды отправляются только по HTTPS на сервер и не сохраняются. Не вводите пароль Steam или Steam Guard.', steamImportBtn:'Получить следующий код', steamImportBusy:'Запрос к Steam…', steamImportResult:'Следующий код матча', steamUpToDate:'Новых матчей нет.', steamSignIn:'Сначала войдите через Steam.', steamImportError:'Не удалось получить код матча.' },
 kz: { eyebrow:'COUNTER-STRIKE 2 · MATCH INTELLIGENCE', title:'Матчтарың. Демо-файлдарың. Талдауың.', subtitle:'Steam және FACEIT матчтары: демо жүктеу, раундтарды талдау және ойыншы статистикасы.', steam:'Steam арқылы кіру', faceitLogin:'FACEIT арқылы кіру', faceit:'FACEIT ойыншысын іздеу', matches:'Матчтар', demos:'Демолар', analytics:'Талдау', replay:'2D Replay', highlights:'Үздік сәттер', recent:'Соңғы матчтар', empty:'Дереккөз қосылғаннан кейін матчтар осында көрінеді. Жалған матчтар көрсетілмейді.', status:'API байланысы тексерілуде…', soon:'Нақты деректер · Жалған матчтарсыз', nickname:'FACEIT никнеймі', search:'Іздеу', loading:'Іздеу…', notConfigured:'FACEIT API серверде бапталмаған. Render-ге FACEIT_API_KEY қосыңыз.', noPlayers:'Ойыншылар табылмады.', steamConnected:'Steam сәтті қосылды.', steamWait:'Steam кіру сервер құпия кілті бапталғаннан кейін қолжетімді болады.', steamImport:'Steam матчтарын импорттау', steamAuthCode:'Game Authentication Code', steamMatchCode:'Соңғы Match Sharing Code', steamImportHelp:'Кодтар тек HTTPS арқылы серверге жіберіледі және сақталмайды. Steam құпиясөзін немесе Steam Guard кодын енгізбеңіз.', steamImportBtn:'Келесі кодты алу', steamImportBusy:'Steam сұрауы…', steamImportResult:'Келесі матч коды', steamUpToDate:'Жаңа матчтар жоқ.', steamSignIn:'Алдымен Steam-ге кіріңіз.', steamImportError:'Матч кодын алу мүмкін болмады.' },
 en: { eyebrow:'COUNTER-STRIKE 2 · MATCH INTELLIGENCE', title:'Your matches. Your demos. Your analysis.', subtitle:'One hub for Steam and FACEIT matches: demo downloads, round review and player analytics.', steam:'Sign in with Steam', faceitLogin:'Sign in with FACEIT', faceit:'Find FACEIT player', matches:'Matches', demos:'Demos', analytics:'Analytics', replay:'2D Replay', highlights:'Highlights', recent:'Recent matches', empty:'Matches appear here after a provider is connected. No fake matches or links.', status:'Checking API connection…', soon:'Live data · No fabricated matches', nickname:'FACEIT nickname', search:'Search', loading:'Searching…', notConfigured:'FACEIT API is not configured on the server. Add FACEIT_API_KEY in Render.', noPlayers:'No players found.', steamConnected:'Steam connected successfully.', steamWait:'Steam sign-in becomes available after the server secret is configured.', steamImport:'Import Steam matches', steamAuthCode:'Game Authentication Code', steamMatchCode:'Latest Match Sharing Code', steamImportHelp:'Codes are sent to the server over HTTPS and are not stored. Never enter your Steam password or Steam Guard code.', steamImportBtn:'Get next code', steamImportBusy:'Contacting Steam…', steamImportResult:'Next match code', steamUpToDate:'No newer matches.', steamSignIn:'Sign in with Steam first.', steamImportError:'Could not retrieve the match code.' }
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
 const [myFaceitMatches,setMyFaceitMatches]=useState<FaceitMatch[]|null>(null);
 const [myFaceitLoading,setMyFaceitLoading]=useState(false);
 const [myFaceitError,setMyFaceitError]=useState('');
 const [faceitMatches,setFaceitMatches] = useState<Record<string,FaceitMatch[]>>({});
 const [matchLoading,setMatchLoading] = useState<string|null>(null);
 const [matchErrors,setMatchErrors] = useState<Record<string,string>>({});
 const [steamAuthCode,setSteamAuthCode] = useState('');
 const [steamMatchCode,setSteamMatchCode] = useState('');
 const [steamImportBusy,setSteamImportBusy] = useState(false);
 const [steamImportError,setSteamImportError] = useState('');
 const [steamImportResult,setSteamImportResult] = useState<SteamImportResult|null>(null);
 const [steamShareCode,setSteamShareCode] = useState('');
 const [steamDecodedMatches,setSteamDecodedMatches] = useState<SteamDecodedMatch[]>([]);
 const [steamDecodeBusy,setSteamDecodeBusy] = useState(false);
 const [steamDecodeError,setSteamDecodeError] = useState('');
 const t = copy[locale];
 useEffect(() => {
   fetch(API + '/api/v1/status').then(async r => { if(!r.ok) throw new Error(); const d=await r.json(); setApiStatus(d.integrations?.faceit_data_api || 'online'); })
     .catch(() => setApiStatus('offline'));
   fetch(API + '/api/v1/auth/me',{credentials:'include'}).then(r=>r.json()).then(d=>{if(d.authenticated)setSteamId(d.steam_id)}).catch(()=>{});
   fetch(API + '/api/v1/auth/faceit/me',{credentials:'include'}).then(r=>r.json()).then(d=>{if(d.authenticated)setFaceitUser({nickname:d.nickname,sub:d.faceit_id,picture:d.picture})}).catch(()=>{});
   try { const saved=window.localStorage.getItem('cs2dh-steam-matches'); if(saved){ const parsed=JSON.parse(saved); if(Array.isArray(parsed))setSteamDecodedMatches(parsed); } } catch {}
 }, []);
 async function loadFaceitMatches(player:FaceitPlayer) {
   setMatchLoading(player.player_id); setMatchErrors(prev=>({...prev,[player.player_id]:''}));
   try {
     const r=await fetch(API+'/api/v1/faceit/players/'+encodeURIComponent(player.player_id)+'/matches?limit=20');
     const data=await r.json();
     if(!r.ok) throw new Error(data.detail || 'Не удалось получить историю FACEIT');
     setFaceitMatches(prev=>({...prev,[player.player_id]:data.items||[]}));
   } catch(err) { setMatchErrors(prev=>({...prev,[player.player_id]:err instanceof Error?err.message:'Ошибка загрузки матчей'})); }
   finally { setMatchLoading(null); }
 }
 function formatMatchDate(value?:number) {
   if(!value) return 'Дата не указана';
   return new Date(value*1000).toLocaleString(locale==='ru'?'ru-RU':locale==='kz'?'kk-KZ':'en-US');
 }
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
 async function loadMyFaceitMatches() {
   setMyFaceitLoading(true); setMyFaceitError('');
   try { const r=await fetch(API+'/api/v1/auth/faceit/matches?limit=20',{credentials:'include'}); const data=await r.json(); if(!r.ok) throw new Error(data.detail||'Не удалось загрузить историю FACEIT'); setMyFaceitMatches(data.items||[]); }
   catch(err) { setMyFaceitError(err instanceof Error?err.message:'Ошибка загрузки матчей'); }
   finally { setMyFaceitLoading(false); }
 }
 const steamLogin = () => { window.location.href=API+'/api/v1/auth/steam/login'; };
 const faceitLogin = () => { window.location.href=API+'/api/v1/auth/faceit/login'; };
 async function decodeAndSaveSteamMatch(rawCode:string) {
   const r=await fetch(API+'/api/v1/steam/matches/decode',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({share_code:rawCode.trim()})});
   const data=await r.json();
   if(!r.ok) throw new Error(data.detail||'Не удалось распознать код матча');
   setSteamDecodedMatches(prev=>prev.some(m=>m.share_code===data.share_code)?prev:[data,...prev].slice(0,50));
   return data as SteamDecodedMatch;
 }
 async function addSteamShareCode(e:FormEvent) {
   e.preventDefault(); setSteamDecodeBusy(true); setSteamDecodeError('');
   try { await decodeAndSaveSteamMatch(steamShareCode); setSteamShareCode(''); }
   catch(err) { setSteamDecodeError(err instanceof Error?err.message:'Ошибка разбора кода'); }
   finally { setSteamDecodeBusy(false); }
 }
 async function importNextSteamMatch(e:FormEvent) {
   e.preventDefault(); setSteamImportBusy(true); setSteamImportError(''); setSteamImportResult(null);
   try { const r=await fetch(API+'/api/v1/steam/matches/next',{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify({authentication_code:steamAuthCode.trim(),known_match_code:steamMatchCode.trim()})}); const data=await r.json(); if(!r.ok) throw new Error(data.detail||t.steamImportError); setSteamImportResult(data); if(data.next_code){setSteamMatchCode(data.next_code); try { await decodeAndSaveSteamMatch(data.next_code); } catch {} } }
   catch(err) { setSteamImportError(err instanceof Error?err.message:t.steamImportError); } finally { setSteamAuthCode(''); setSteamImportBusy(false); }
 }
 return <main className="shell"><header className="topbar"><a className="brand" href="#"><span className="brand-mark">D</span><span>CS2 <b>DEMO HUB</b></span></a><nav><a href="#matches">{t.matches}</a><a href="#analytics">{t.analytics}</a><a href="#replay">{t.replay}</a></nav><div className="locale">{(['ru','kz','en'] as Locale[]).map(x=><button key={x} className={locale===x?'active':''} onClick={()=>setLocale(x)}>{x.toUpperCase()}</button>)}</div></header>
 <section className="hero"><div className="hero-copy"><div className="eyebrow"><span className="pulse"/>{t.eyebrow}</div><h1>{t.title}</h1><p>{t.subtitle}</p><div className="actions"><button className="primary" onClick={faceitLogin}>{faceitUser ? 'FACEIT · '+(faceitUser.nickname||faceitUser.sub||'connected') : t.faceitLogin} ↗</button><button className="secondary" onClick={steamLogin}>{steamId ? 'Steam · '+steamId : t.steam} ↗</button><a className="secondary button-link" href="#faceit">{t.faceit} ↗</a>{faceitUser&&<button className="secondary" type="button" onClick={loadMyFaceitMatches} disabled={myFaceitLoading}>{myFaceitLoading?'Загрузка…':'Мои матчи FACEIT'}</button>}</div><div className="fine">{faceitUser ? 'FACEIT account connected · '+(faceitUser.nickname||faceitUser.sub||'') : (steamId ? t.steamConnected : t.status+' '+apiStatus)}</div></div><div className="hero-art"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="crosshair">✛</div><div className="art-label">DEMO<br/><strong>INTELLIGENCE</strong></div><div className="art-bottom">STEAM <i>×</i> FACEIT <i>×</i> CS2</div></div></section>
 <section className="stats" id="analytics">{[[t.matches,'—','MATCH DATABASE'],[t.demos,'—','DEMO STORAGE'],[t.analytics,'—','PLAYER METRICS'],[t.highlights,'—','VIDEO EXPORT']].map(([label,value,sub])=><article className="stat" key={sub}><span>{sub}</span><strong>{value}</strong><small>{label}</small></article>)}</section>
 <section className="content-grid" id="matches"><article className="panel recent"><div className="panel-head"><div><span className="eyebrow">MATCH CENTER</span><h2>{t.recent}</h2></div><span className="tag">LIVE DATA ONLY</span></div><div className="empty"><div className="empty-icon">⌁</div><p>{t.empty}</p></div></article><article className="panel modules" id="replay"><span className="eyebrow">YOUR WORKSPACE</span><h2>Modules</h2>{[t.demos,t.analytics,t.replay,t.highlights].map((x,i)=><div className="module-row" key={x}><span className="module-number">0{i+1}</span><b>{x}</b><span className="module-state">{i===0?'API INTEGRATION':'PLANNED'}</span></div>)}</article></section>
 <section className="panel faceit-panel" id="my-faceit-matches"><div className="panel-head"><div><span className="eyebrow">CONNECTED ACCOUNT</span><h2>Мои матчи FACEIT</h2></div></div>{myFaceitError&&<p className="error-message">{myFaceitError}</p>}{myFaceitMatches&&<div className="match-list">{myFaceitMatches.length===0?<p>Матчи не найдены.</p>:myFaceitMatches.map(m=><div className="module-row" key={m.match_id}><div><b>{m.map||"Карта не указана"}</b><small>{formatMatchDate(m.started_at)} · {m.game_mode||"CS2"}</small></div><span className="module-state">{m.demo_available?"ДЕМО ЕСТЬ":"ДЕМО НЕТ"}</span></div>)}</div>}</section>
 <section className="panel faceit-panel" id="steam-import"><div className="panel-head"><div><span className="eyebrow">STEAM MATCH SHARING</span><h2>{t.steamImport}</h2></div><span className="tag">{steamId?'STEAM CONNECTED':'SIGN IN REQUIRED'}</span></div><p className="fine">{t.steamImportHelp}</p><form className="faceit-search" onSubmit={importNextSteamMatch}><input type="password" autoComplete="off" value={steamAuthCode} onChange={e=>setSteamAuthCode(e.target.value.toUpperCase())} placeholder={t.steamAuthCode} minLength={10} maxLength={32} required disabled={!steamId||steamImportBusy}/><input type="text" autoComplete="off" value={steamMatchCode} onChange={e=>setSteamMatchCode(e.target.value.toUpperCase())} placeholder={t.steamMatchCode} minLength={20} maxLength={64} required disabled={!steamId||steamImportBusy}/><button className="primary" type="submit" disabled={!steamId||steamImportBusy||!steamAuthCode.trim()||!steamMatchCode.trim()}>{steamImportBusy?t.steamImportBusy:t.steamImportBtn}</button></form>{!steamId&&<p className="error-message">{t.steamSignIn}</p>}{steamImportError&&<p className="error-message">{steamImportError}</p>}{steamImportResult&&<div className="module-row"><div><b>{steamImportResult.status==='up_to_date'?t.steamUpToDate:t.steamImportResult}</b><small>{steamImportResult.message||''}</small>{steamImportResult.next_code&&<code>{steamImportResult.next_code}</code>}</div></div>}</section>
 <section className="panel faceit-panel" id="steam-matches"><div className="panel-head"><div><span className="eyebrow">VALVE MATCH SHARING</span><h2>Импорт демо-матча Steam</h2></div><span className="tag">{steamDecodedMatches.length} SAVED</span></div><p className="fine">Вставь код матча CSGO- из CS2 → Смотреть → Ваши матчи. Код проверяется на сервере, а список хранится в этом браузере. Данные карты и счёт появятся после подключения Game Coordinator.</p><form className="faceit-search" onSubmit={addSteamShareCode}><input value={steamShareCode} onChange={e=>setSteamShareCode(e.target.value)} placeholder="CSGO-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX" minLength={34} maxLength={34} required disabled={steamDecodeBusy}/><button className="primary" type="submit" disabled={steamDecodeBusy||steamShareCode.trim().length!==34}>{steamDecodeBusy?'Проверка…':'Добавить матч'}</button></form>{steamDecodeError&&<p className="error-message">{steamDecodeError}</p>}{steamDecodedMatches.length===0?<div className="empty"><p>Пока нет добавленных матчей Steam.</p></div>:<div className="match-list">{steamDecodedMatches.map(m=><div className="module-row" key={m.share_code}><div><b>Valve Match · {m.match_id}</b><small>{m.share_code}</small><small>Метаданные и демо-ссылка пока не получены</small></div><a className="button-link" href={m.steam_launch_uri}>Открыть в CS2 ↗</a></div>)}</div>}</section>
 <section className="panel faceit-panel" id="faceit"><div className="panel-head"><div><span className="eyebrow">FACEIT DATA API</span><h2>{t.faceit}</h2></div><span className="tag">{apiStatus==='configured'?'CONNECTED':'SETUP REQUIRED'}</span></div><form className="faceit-search" onSubmit={searchFaceit}><input value={nickname} onChange={e=>setNickname(e.target.value)} placeholder={t.nickname} minLength={2} maxLength={32}/><button className="primary" disabled={busy||nickname.trim().length<2}>{busy?t.loading:t.search}</button></form>{error&&<p className="error-message">{error}</p>}{players.length>0&&<div className="players-list">{players.map(p=><article className="player-card" key={p.player_id}><div className="player-avatar">{p.avatar?<img src={p.avatar} alt=""/>:<span>{p.nickname?.slice(0,1)?.toUpperCase()}</span>}</div><div><b>{p.nickname}</b><small>{p.country||'—'} · {p.games?.cs2?.faceit_elo ? p.games.cs2.faceit_elo+' ELO' : 'CS2'}</small></div><button className="secondary" type="button" disabled={matchLoading===p.player_id} onClick={()=>loadFaceitMatches(p)}>{matchLoading===p.player_id?'Загрузка…':'Показать матчи'}</button>{matchErrors[p.player_id]&&<p className="error-message">{matchErrors[p.player_id]}</p>}{faceitMatches[p.player_id]&&<div className="match-list">{faceitMatches[p.player_id].length===0?<p>История матчей не найдена.</p>:faceitMatches[p.player_id].map(m=><div className="module-row" key={m.match_id}><div><b>{m.map||'Карта не указана'}</b><small>{formatMatchDate(m.started_at)} · {m.game_mode||'CS2'}</small></div><span className="module-state">{m.demo_available?'ДЕМО ЕСТЬ':'ДЕМО НЕ УКАЗАНО'}</span></div>)}</div>}</article>)}</div>}</section>
 <footer><span>CS2 DEMO HUB · FOUNDATION 0.2.0</span><span>{t.soon}</span></footer></main>;
}
