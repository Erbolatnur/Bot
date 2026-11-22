'use client';
import { FormEvent, useEffect, useState } from 'react';

type Locale = 'ru' | 'kz' | 'en';
type FaceitPlayer = { player_id: string; nickname: string; avatar?: string; country?: string; games?: Record<string, { skill_level?: number; faceit_elo?: number }> };
type FaceitMatch = { match_id: string; started_at?: number; finished_at?: number; game_mode?: string; map?: string | null; demo_available?: boolean };
type SteamImportResult = { status: string; next_code: string | null; message?: string };
type SteamDecodedMatch = { share_code:string; match_id:string; reservation_id:string; tv_port:number; steam_launch_uri:string; metadata_available:boolean };
type Project = { id:string; title:string; description:string; status:string; updated_at?:string };
type SavedMatch = { provider:string; match_id:string; payload:Record<string, unknown>; created_at?:string; updated_at?:string };
type DemoRecord = { id:string; filename:string; size_bytes:number; status:string; analysis?:{rounds_started?:number;rounds_ended?:number;deaths_total?:number;kills_by_player?:{player:string;kills:number}[]}; created_at?:string };
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
 const [faceitDemoUrls,setFaceitDemoUrls] = useState<Record<string,string>>({});
 const [faceitDemoLoading,setFaceitDemoLoading] = useState<string|null>(null);
 const [faceitDemoErrors,setFaceitDemoErrors] = useState<Record<string,string>>({});
 const [steamAuthCode,setSteamAuthCode] = useState('');
 const [steamMatchCode,setSteamMatchCode] = useState('');
 const [steamImportBusy,setSteamImportBusy] = useState(false);
 const [steamImportError,setSteamImportError] = useState('');
 const [steamImportResult,setSteamImportResult] = useState<SteamImportResult|null>(null);
 const [steamShareCode,setSteamShareCode] = useState('');
 const [steamDecodedMatches,setSteamDecodedMatches] = useState<SteamDecodedMatch[]>([]);
 const [steamStorageLoaded,setSteamStorageLoaded] = useState(false);
 const [steamDecodeBusy,setSteamDecodeBusy] = useState(false);
 const [steamDecodeError,setSteamDecodeError] = useState('');
 const [projects,setProjects] = useState<Project[]>([]);
 const [unifiedMatches,setUnifiedMatches] = useState<SavedMatch[]>([]);
 const [matchesLoading,setMatchesLoading] = useState(false);
 const [matchesError,setMatchesError] = useState('');
 const [matchSourceFilter,setMatchSourceFilter] = useState('all');
 const [matchMapFilter,setMatchMapFilter] = useState('all');
 const [matchDateFilter,setMatchDateFilter] = useState('all');
 const [projectTitle,setProjectTitle] = useState('');
 const [projectBusy,setProjectBusy] = useState(false);
 const [projectError,setProjectError] = useState('');
 const [demos,setDemos] = useState<DemoRecord[]>([]);
 const [demoFile,setDemoFile] = useState<File|null>(null);
 const [demoBusy,setDemoBusy] = useState(false);
 const [demoError,setDemoError] = useState('');
 const t = copy[locale];
 useEffect(() => {
   fetch(API + '/api/v1/status').then(async r => { if(!r.ok) throw new Error(); const d=await r.json(); setApiStatus(d.integrations?.faceit_data_api || 'online'); })
     .catch(() => setApiStatus('offline'));
   fetch(API + '/api/v1/auth/me',{credentials:'include'}).then(r=>r.json()).then(d=>{if(d.authenticated){setSteamId(d.steam_id); void loadProjects(); void loadUnifiedMatches(); void loadDemos();}}).catch(()=>{});
   fetch(API + '/api/v1/auth/faceit/me',{credentials:'include'}).then(r=>r.json()).then(d=>{if(d.authenticated){setFaceitUser({nickname:d.nickname,sub:d.faceit_id,picture:d.picture}); void loadProjects(); void loadUnifiedMatches();}}).catch(()=>{});
   try { const saved=window.localStorage.getItem('cs2dh-steam-matches'); if(saved){ const parsed=JSON.parse(saved); if(Array.isArray(parsed))setSteamDecodedMatches(parsed); } } catch {}
   setSteamStorageLoaded(true);
 }, []);
 useEffect(()=>{ if(!steamStorageLoaded)return; try { window.localStorage.setItem('cs2dh-steam-matches',JSON.stringify(steamDecodedMatches)); } catch {} },[steamDecodedMatches,steamStorageLoaded]);
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
 async function loadFaceitDemoUrl(matchId:string) {
   setFaceitDemoLoading(matchId); setFaceitDemoErrors(prev=>({...prev,[matchId]:''}));
   try {
     const r=await fetch(API+'/api/v1/faceit/matches/'+encodeURIComponent(matchId)+'/demo-download-url');
     const data=await r.json();
     if(!r.ok) throw new Error(data.detail||'Не удалось получить ссылку на демо');
     if(typeof data.download_url!=='string'||!data.download_url.startsWith('https://')) throw new Error('FACEIT вернул некорректную ссылку');
     setFaceitDemoUrls(prev=>({...prev,[matchId]:data.download_url}));
   } catch(err) { setFaceitDemoErrors(prev=>({...prev,[matchId]:err instanceof Error?err.message:'Ошибка получения демо'})); }
   finally { setFaceitDemoLoading(null); }
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
   try { const r=await fetch(API+'/api/v1/auth/faceit/matches?limit=20',{credentials:'include'}); const data=await r.json(); if(!r.ok) throw new Error(data.detail||'Не удалось загрузить историю FACEIT'); setMyFaceitMatches(data.items||[]); await loadUnifiedMatches(); }
   catch(err) { setMyFaceitError(err instanceof Error?err.message:'Ошибка загрузки матчей'); }
   finally { setMyFaceitLoading(false); }
 }
 const steamLogin = () => { window.location.href=API+'/api/v1/auth/steam/login'; };
 const faceitLogin = () => { window.location.href=API+'/api/v1/auth/faceit/login'; };
 async function loadProjects() {
   try {
     const r=await fetch(API+'/api/v1/projects',{credentials:'include'});
     if(r.status===401||r.status===503)return;
     const data=await r.json();
     if(!r.ok) throw new Error(data.detail||'Не удалось загрузить проекты');
     setProjects(data.items||[]);
   } catch(err) { setProjectError(err instanceof Error?err.message:'Ошибка загрузки проектов'); }
 }
 async function loadUnifiedMatches() {
   setMatchesLoading(true); setMatchesError('');
   try {
     const r=await fetch(API+'/api/v1/matches?source=all&limit=100',{credentials:'include'});
     const data=await r.json();
     if(!r.ok) throw new Error(data.detail||'Не удалось загрузить сохранённые матчи');
     setUnifiedMatches(Array.isArray(data.items)?data.items:[]);
   } catch(err) { setMatchesError(err instanceof Error?err.message:'Ошибка загрузки матчей'); }
   finally { setMatchesLoading(false); }
 }
 const availableMaps=Array.from(new Set(unifiedMatches.map(m=>String(m.payload?.map||'')).filter(Boolean))).sort();
 const filteredMatches=unifiedMatches.filter(m=>{
   if(matchSourceFilter!=='all' && m.provider!==matchSourceFilter) return false;
   if(matchMapFilter!=='all' && String(m.payload?.map||'')!==matchMapFilter) return false;
   if(matchDateFilter!=='all') {
     const fromPayload=Number(m.payload?.started_at||0)*1000;
     const timestamp=fromPayload || Date.parse(m.created_at||'') || 0;
     if(!timestamp || timestamp < Date.now()-Number(matchDateFilter)*86400000) return false;
   }
   return true;
 });
 async function loadDemos() {
   try { const r=await fetch(API+'/api/v1/demos',{credentials:'include'}); if(r.status===401||r.status===503)return; const data=await r.json(); if(!r.ok)throw new Error(data.detail||'Не удалось загрузить демо'); setDemos(data.items||[]); }
   catch(err) { setDemoError(err instanceof Error?err.message:'Ошибка загрузки демок'); }
 }
 async function uploadDemo(e:FormEvent) {
   e.preventDefault(); if(!demoFile)return;
   setDemoBusy(true); setDemoError('');
   try {
     const form=new FormData(); form.append('file',demoFile);
     const r=await fetch(API+'/api/v1/demos',{method:'POST',credentials:'include',body:form});
     const data=await r.json(); if(!r.ok)throw new Error(data.detail||'Не удалось загрузить демо');
     setDemos(prev=>[data.item,...prev]); setDemoFile(null);
     const input=document.getElementById('demo-file-input') as HTMLInputElement|null; if(input)input.value='';
   } catch(err) { setDemoError(err instanceof Error?err.message:'Ошибка загрузки или разбора демо'); }
   finally { setDemoBusy(false); }
 }
 async function removeDemo(id:string) {
   setDemoError('');
   try { const r=await fetch(API+'/api/v1/demos/'+encodeURIComponent(id),{method:'DELETE',credentials:'include'}); const data=await r.json(); if(!r.ok)throw new Error(data.detail||'Не удалось удалить демо'); setDemos(prev=>prev.filter(d=>d.id!==id)); }
   catch(err) { setDemoError(err instanceof Error?err.message:'Ошибка удаления демо'); }
 }
 async function createProject(e:FormEvent) {
   e.preventDefault(); if(!projectTitle.trim())return;
   setProjectBusy(true); setProjectError('');
   try {
     const r=await fetch(API+'/api/v1/projects',{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:projectTitle.trim()})});
     const data=await r.json();
     if(!r.ok) throw new Error(data.detail||'Не удалось создать проект');
     setProjects(prev=>[data.item,...prev]); setProjectTitle('');
   } catch(err) { setProjectError(err instanceof Error?err.message:'Ошибка создания проекта'); }
   finally { setProjectBusy(false); }
 }
 async function deleteProject(id:string) {
   setProjectError('');
   try {
     const r=await fetch(API+'/api/v1/projects/'+encodeURIComponent(id),{method:'DELETE',credentials:'include'});
     const data=await r.json();
     if(!r.ok) throw new Error(data.detail||'Не удалось удалить проект');
     setProjects(prev=>prev.filter(p=>p.id!==id));
   } catch(err) { setProjectError(err instanceof Error?err.message:'Ошибка удаления проекта'); }
 }
 async function decodeAndSaveSteamMatch(rawCode:string) {
   const r=await fetch(API+'/api/v1/steam/matches/decode',{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify({share_code:rawCode.trim()})});
   const data=await r.json();
   if(!r.ok) throw new Error(data.detail||'Не удалось распознать код матча');
   setSteamDecodedMatches(prev=>prev.some(m=>m.share_code===data.share_code)?prev:[data,...prev].slice(0,50));
   return data as SteamDecodedMatch;
 }
 async function addSteamShareCode(e:FormEvent) {
   e.preventDefault(); setSteamDecodeBusy(true); setSteamDecodeError('');
   try { await decodeAndSaveSteamMatch(steamShareCode); setSteamShareCode(''); await loadUnifiedMatches(); }
   catch(err) { setSteamDecodeError(err instanceof Error?err.message:'Ошибка разбора кода'); }
   finally { setSteamDecodeBusy(false); }
 }
 async function importNextSteamMatch(e:FormEvent) {
   e.preventDefault(); setSteamImportBusy(true); setSteamImportError(''); setSteamImportResult(null);
   try { const r=await fetch(API+'/api/v1/steam/matches/next',{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify({authentication_code:steamAuthCode.trim(),known_match_code:steamMatchCode.trim()})}); const data=await r.json(); if(!r.ok) throw new Error(data.detail||t.steamImportError); setSteamImportResult(data); if(data.next_code){setSteamMatchCode(data.next_code); try { await decodeAndSaveSteamMatch(data.next_code); } catch {} } await loadUnifiedMatches(); }
   catch(err) { setSteamImportError(err instanceof Error?err.message:t.steamImportError); } finally { setSteamAuthCode(''); setSteamImportBusy(false); }
 }
 return <main className="shell"><header className="topbar"><a className="brand" href="#"><span className="brand-mark">D</span><span>CS2 <b>DEMO HUB</b></span></a><nav><a href="#matches">{t.matches}</a><a href="#analytics">{t.analytics}</a><a href="#replay">{t.replay}</a></nav><div className="locale">{(['ru','kz','en'] as Locale[]).map(x=><button key={x} className={locale===x?'active':''} onClick={()=>setLocale(x)}>{x.toUpperCase()}</button>)}</div></header>
 <section className="hero"><div className="hero-copy"><div className="eyebrow"><span className="pulse"/>{t.eyebrow}</div><h1>{t.title}</h1><p>{t.subtitle}</p><div className="actions"><button className="primary" onClick={faceitLogin}>{faceitUser ? 'FACEIT · '+(faceitUser.nickname||faceitUser.sub||'connected') : t.faceitLogin} ↗</button><button className="secondary" onClick={steamLogin}>{steamId ? 'Steam · '+steamId : t.steam} ↗</button><a className="secondary button-link" href="#faceit">{t.faceit} ↗</a>{faceitUser&&<button className="secondary" type="button" onClick={loadMyFaceitMatches} disabled={myFaceitLoading}>{myFaceitLoading?'Загрузка…':'Мои матчи FACEIT'}</button>}</div><div className="fine">{faceitUser ? 'FACEIT account connected · '+(faceitUser.nickname||faceitUser.sub||'') : (steamId ? t.steamConnected : t.status+' '+apiStatus)}</div></div><div className="hero-art"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="crosshair">✛</div><div className="art-label">DEMO<br/><strong>INTELLIGENCE</strong></div><div className="art-bottom">STEAM <i>×</i> FACEIT <i>×</i> CS2</div></div></section>
 <section className="stats" id="analytics">{[[t.matches,'—','MATCH DATABASE'],[t.demos,'—','DEMO STORAGE'],[t.analytics,'—','PLAYER METRICS'],[t.highlights,'—','VIDEO EXPORT']].map(([label,value,sub])=><article className="stat" key={sub}><span>{sub}</span><strong>{value}</strong><small>{label}</small></article>)}</section>
 <section className="content-grid" id="matches"><article className="panel recent"><div className="panel-head"><div><span className="eyebrow">MATCH CENTER</span><h2>{t.recent}</h2></div><span className="tag">LIVE DATA ONLY</span></div><div className="match-filters"><select aria-label="Источник матчей" value={matchSourceFilter} onChange={e=>setMatchSourceFilter(e.target.value)}><option value="all">Все источники</option><option value="faceit">FACEIT</option><option value="steam">Steam</option></select><select aria-label="Карта" value={matchMapFilter} onChange={e=>setMatchMapFilter(e.target.value)}><option value="all">Все карты</option>{availableMaps.map(map=><option key={map} value={map}>{map}</option>)}</select><select aria-label="Период" value={matchDateFilter} onChange={e=>setMatchDateFilter(e.target.value)}><option value="all">За всё время</option><option value="7">7 дней</option><option value="30">30 дней</option></select><button className="secondary" type="button" onClick={loadUnifiedMatches} disabled={matchesLoading}>{matchesLoading?'Обновление…':'Обновить'}</button></div>{matchesError&&<p className="error-message">{matchesError}</p>}{matchesLoading&&unifiedMatches.length===0?<div className="empty"><p>Загружаем сохранённые матчи…</p></div>:filteredMatches.length===0?<div className="empty"><div className="empty-icon">⌁</div><p>{unifiedMatches.length===0?'Сохранённых матчей пока нет. Войди через Steam или FACEIT и загрузи историю матчей.': 'По выбранным фильтрам матчей нет.'}</p></div>:<div className="unified-match-list">{filteredMatches.map(m=><div className="unified-match-card" key={`${m.provider}:${m.match_id}`}><div className="match-provider">{m.provider==='faceit'?'FACEIT':'STEAM'}</div><div className="match-main"><b>{String(m.payload?.map||'Карта не указана')}</b><small>{m.provider==='faceit'?'FACEIT match':'Valve match'} · {String(m.match_id)}</small><small>{(typeof m.payload?.started_at==='number'?formatMatchDate(m.payload.started_at):(m.created_at?new Date(m.created_at).toLocaleString(locale==='ru'?'ru-RU':locale==='kz'?'kk-KZ':'en-US'):'Дата не указана'))}</small></div><div className="match-status">{m.provider==='faceit'?(m.payload?.demo_available?'ДЕМО ЕСТЬ':'ДЕМО НЕ УКАЗАНО'):'КОД СОХРАНЁН'}</div>{typeof m.payload?.share_code==='string'&&<a className="button-link" href={`steam://run/730//+csgo_download_match%20${encodeURIComponent(m.payload.share_code)}`}>Открыть в CS2 ↗</a>}</div>)}</div>}</article><article className="panel modules" id="replay"><span className="eyebrow">YOUR WORKSPACE</span><h2>Modules</h2>{[t.demos,t.analytics,t.replay,t.highlights].map((x,i)=><div className="module-row" key={x}><span className="module-number">0{i+1}</span><b>{x}</b><span className="module-state">{i===0?'API INTEGRATION':'PLANNED'}</span></div>)}</article></section>
 <section className="panel faceit-panel" id="my-faceit-matches"><div className="panel-head"><div><span className="eyebrow">CONNECTED ACCOUNT</span><h2>Мои матчи FACEIT</h2></div></div>{myFaceitError&&<p className="error-message">{myFaceitError}</p>}{myFaceitMatches&&<div className="match-list">{myFaceitMatches.length===0?<p>Матчи не найдены.</p>:myFaceitMatches.map(m=><div className="module-row" key={m.match_id}><div><b>{m.map||"Карта не указана"}</b><small>{formatMatchDate(m.started_at)} · {m.game_mode||"CS2"}</small></div><span className="module-state">{m.demo_available?"ДЕМО ЕСТЬ":"ДЕМО НЕТ"}</span>{m.demo_available&&(faceitDemoUrls[m.match_id]?<a className="button-link" href={faceitDemoUrls[m.match_id]} target="_blank" rel="noopener noreferrer">Скачать демо ↗</a>:<button className="secondary" type="button" disabled={faceitDemoLoading===m.match_id} onClick={()=>loadFaceitDemoUrl(m.match_id)}>{faceitDemoLoading===m.match_id?"Получаем ссылку…":"Получить ссылку на демо"}</button>)}{faceitDemoErrors[m.match_id]&&<small className="error-message">{faceitDemoErrors[m.match_id]}</small>}</div>)}</div>}</section>
 <section className="panel faceit-panel" id="steam-import"><div className="panel-head"><div><span className="eyebrow">STEAM MATCH SHARING</span><h2>{t.steamImport}</h2></div><span className="tag">{steamId?'STEAM CONNECTED':'SIGN IN REQUIRED'}</span></div><p className="fine">{t.steamImportHelp}</p><form className="faceit-search" onSubmit={importNextSteamMatch}><input type="password" autoComplete="off" value={steamAuthCode} onChange={e=>setSteamAuthCode(e.target.value.toUpperCase())} placeholder={t.steamAuthCode} minLength={10} maxLength={32} required disabled={!steamId||steamImportBusy}/><input type="text" autoComplete="off" value={steamMatchCode} onChange={e=>setSteamMatchCode(e.target.value.toUpperCase())} placeholder={t.steamMatchCode} minLength={20} maxLength={64} required disabled={!steamId||steamImportBusy}/><button className="primary" type="submit" disabled={!steamId||steamImportBusy||!steamAuthCode.trim()||!steamMatchCode.trim()}>{steamImportBusy?t.steamImportBusy:t.steamImportBtn}</button></form>{!steamId&&<p className="error-message">{t.steamSignIn}</p>}{steamImportError&&<p className="error-message">{steamImportError}</p>}{steamImportResult&&<div className="module-row"><div><b>{steamImportResult.status==='up_to_date'?t.steamUpToDate:t.steamImportResult}</b><small>{steamImportResult.message||''}</small>{steamImportResult.next_code&&<code>{steamImportResult.next_code}</code>}</div></div>}</section>
 <section className="panel faceit-panel" id="steam-matches"><div className="panel-head"><div><span className="eyebrow">VALVE MATCH SHARING</span><h2>Импорт демо-матча Steam</h2></div><span className="tag">{steamDecodedMatches.length} SAVED</span></div><p className="fine">Вставь код матча CSGO- из CS2 → Смотреть → Ваши матчи. Код проверяется на сервере; при входе через Steam он также сохраняется в твоей истории аккаунта. Данные карты и счёт появятся после подключения Game Coordinator.</p><form className="faceit-search" onSubmit={addSteamShareCode}><input value={steamShareCode} onChange={e=>setSteamShareCode(e.target.value)} placeholder="CSGO-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX" minLength={34} maxLength={34} required disabled={steamDecodeBusy}/><button className="primary" type="submit" disabled={steamDecodeBusy||steamShareCode.trim().length!==34}>{steamDecodeBusy?'Проверка…':'Добавить матч'}</button></form>{steamDecodeError&&<p className="error-message">{steamDecodeError}</p>}{steamDecodedMatches.length===0?<div className="empty"><p>Пока нет добавленных матчей Steam.</p></div>:<div className="match-list">{steamDecodedMatches.map(m=><div className="module-row" key={m.share_code}><div><b>Valve Match · {m.match_id}</b><small>{m.share_code}</small><small>Метаданные и демо-ссылка пока не получены</small></div><a className="button-link" href={m.steam_launch_uri}>Открыть в CS2 ↗</a></div>)}</div>}</section>
  <section className="panel faceit-panel" id="demo-library"><div className="panel-head"><div><span className="eyebrow">CS2 DEMO PARSER</span><h2>Загрузка и анализ демок</h2></div><span className="tag">{demos.length} FILES</span></div><p className="fine">Загрузи настоящий файл .dem (до 100 МБ). Сервер проверит формат, сохранит файл в PostgreSQL и извлечёт раунды и события убийств. Файлы доступны только твоему аккаунту.</p><form className="faceit-search" onSubmit={uploadDemo}><input id="demo-file-input" type="file" accept=".dem" onChange={e=>setDemoFile(e.target.files?.[0]||null)} disabled={demoBusy} required/><button className="primary" type="submit" disabled={!demoFile||demoBusy}>{demoBusy?'Загрузка и анализ…':'Загрузить и разобрать'}</button></form>{demoError&&<p className="error-message">{demoError}</p>}{demos.length===0?<div className="empty"><p>Пока нет загруженных демок. Выбери файл .dem для начала анализа.</p></div>:<div className="match-list">{demos.map(d=><div className="module-row" key={d.id}><div><b>{d.filename}</b><small>{(d.size_bytes/1048576).toFixed(1)} МБ · {d.status} · Раундов: {d.analysis?.rounds_ended??'—'} · Убийств: {d.analysis?.deaths_total??'—'}</small>{(d.analysis?.kills_by_player||[]).slice(0,5).map(p=><small key={p.player}>{p.player}: {p.kills} убийств</small>)}</div><a className="button-link" href={API+'/api/v1/demos/'+encodeURIComponent(d.id)+'/download'}>Скачать .dem ↗</a><button className="secondary" type="button" onClick={()=>removeDemo(d.id)}>Удалить</button></div>)}</div>}</section>
 <section className="panel faceit-panel" id="faceit"><div className="panel-head"><div><span className="eyebrow">FACEIT DATA API</span><h2>{t.faceit}</h2></div><span className="tag">{apiStatus==='configured'?'CONNECTED':'SETUP REQUIRED'}</span></div><form className="faceit-search" onSubmit={searchFaceit}><input value={nickname} onChange={e=>setNickname(e.target.value)} placeholder={t.nickname} minLength={2} maxLength={32}/><button className="primary" disabled={busy||nickname.trim().length<2}>{busy?t.loading:t.search}</button></form>{error&&<p className="error-message">{error}</p>}{players.length>0&&<div className="players-list">{players.map(p=><article className="player-card" key={p.player_id}><div className="player-avatar">{p.avatar?<img src={p.avatar} alt=""/>:<span>{p.nickname?.slice(0,1)?.toUpperCase()}</span>}</div><div><b>{p.nickname}</b><small>{p.country||'—'} · {p.games?.cs2?.faceit_elo ? p.games.cs2.faceit_elo+' ELO' : 'CS2'}</small></div><button className="secondary" type="button" disabled={matchLoading===p.player_id} onClick={()=>loadFaceitMatches(p)}>{matchLoading===p.player_id?'Загрузка…':'Показать матчи'}</button>{matchErrors[p.player_id]&&<p className="error-message">{matchErrors[p.player_id]}</p>}{faceitMatches[p.player_id]&&<div className="match-list">{faceitMatches[p.player_id].length===0?<p>История матчей не найдена.</p>:faceitMatches[p.player_id].map(m=><div className="module-row" key={m.match_id}><div><b>{m.map||'Карта не указана'}</b><small>{formatMatchDate(m.started_at)} · {m.game_mode||'CS2'}</small></div><span className="module-state">{m.demo_available?'ДЕМО ЕСТЬ':'ДЕМО НЕ УКАЗАНО'}</span>{m.demo_available&&(faceitDemoUrls[m.match_id]?<a className="button-link" href={faceitDemoUrls[m.match_id]} target="_blank" rel="noopener noreferrer">Скачать демо ↗</a>:<button className="secondary" type="button" disabled={faceitDemoLoading===m.match_id} onClick={()=>loadFaceitDemoUrl(m.match_id)}>{faceitDemoLoading===m.match_id?"Получаем ссылку…":"Получить ссылку на демо"}</button>)}{faceitDemoErrors[m.match_id]&&<small className="error-message">{faceitDemoErrors[m.match_id]}</small>}</div>)}</div>}</article>)}</div>}</section>
 <section className="panel faceit-panel" id="projects"><div className="panel-head"><div><span className="eyebrow">PROJECT WORKSPACE</span><h2>Мои проекты</h2></div><span className="tag">{projects.length} SAVED</span></div><form className="faceit-search" onSubmit={createProject}><input value={projectTitle} onChange={e=>setProjectTitle(e.target.value)} placeholder="Название проекта" maxLength={120} required/><button className="primary" type="submit" disabled={projectBusy||!projectTitle.trim()}>{projectBusy?'Создание…':'Создать проект'}</button></form>{projectError&&<p className="error-message">{projectError}</p>}{projects.length===0?<div className="empty"><p>Проекты появятся после входа и подключения базы данных.</p></div>:<div className="match-list">{projects.map(p=><div className="module-row" key={p.id}><div><b>{p.title}</b><small>{p.description||'Проект CS2 DEMO HUB'} · {p.status}</small></div><button className="secondary" type="button" onClick={()=>deleteProject(p.id)}>Удалить</button></div>)}</div>}</section>
 <nav className="app-bottom-nav" aria-label="Основная навигация">
  <a href="#my-faceit-matches"><span>▦</span><small>Матчи</small></a>
  <a href="#steam-matches"><span>▣</span><small>Демки</small></a>
  <a href="#faceit"><span>◎</span><small>Игроки</small></a>
  <a href="#projects"><span>☰</span><small>Проекты</small></a>
  <a href="#analytics"><span>▥</span><small>Статистика</small></a>
 </nav>
 <footer><span>CS2 DEMO HUB · FOUNDATION 0.2.0</span><span>{t.soon}</span></footer></main>;
}
