var Es=[4,4,0,0],ks=[0,0,4,4],Et=r=>r!==null&&typeof r=="object"&&!Array.isArray(r),Ss=r=>{let e=Et(r)?r.value:r;return Array.isArray(e)?e[1]:e},Ce=(r,e)=>{let t=Et(r)?{...r}:{value:r};return{...t,itemStyle:{...t.itemStyle,...e}}},ue=r=>{let e=Math.max(...r.map(({data:s})=>s.length),0),t=r.map(({data:s})=>[...s]);for(let s of As(r))for(let o=0;o<e;o++)Os(t,o,s);return r.map((s,o)=>({...s,data:t[o]}))},As=r=>{let e=new Map;return r.forEach((t,s)=>{let o=t.stack??Symbol(s),n=e.get(o);n?n.push(s):e.set(o,[s])}),[...e.values()]},Os=(r,e,t)=>{let s=!1,o=!1;for(let n=t.length-1;n>=0;n--){let a=t[n],i=r[a][e];if(i===void 0)continue;let c=Ss(i);c?c>0&&!s?(r[a][e]=Ce(i,{borderRadius:Es}),s=!0):c<0&&!o&&(r[a][e]=Ce(i,{borderRadius:ks}),o=!0):r[a][e]=Ce(i,{borderWidth:0})}};var kt="_energy",Fe="energy_";var Ts=(r,e)=>{let t=r||(e?`${Fe}${e}`:"");return t?t.startsWith(Fe)?`_${t}`:`_${Fe}${t}`:kt},$s=(r,e)=>typeof r=="string"&&r.startsWith(kt)&&e!==null&&typeof e=="object"&&typeof e.subscribe=="function"&&"start"in e,Cs=(r=new Date)=>{let e=new Date(r);return e.setDate(e.getDate()-30),e.setHours(0,0,0,0),{start:e,end:r,fallback:!0}},Fs=r=>{let e=r?.connection;if(!e)return{};let t={};for(let s of Object.keys(e)){let o;try{o=e[s]}catch{continue}$s(s,o)&&(t[s]=o)}return t},Rs=(r,e)=>{let t=Fs(r),s=Ts(e,r?.panelUrl);if(t[s])return t[s];let[o]=Object.values(t);return o??null},Is=r=>r?.startCompare&&r?.endCompare?{compare:{start:r.startCompare,end:r.endCompare,mode:r.compareMode}}:{},St=(r,e,t)=>{let s=null,o=null,n=0,a=r,i=l=>{if(s)return!0;let d=Rs(l,e);if(!d)return!1;let h=p=>t({start:d.start,end:d.end,fallback:!1,...Is(p)});return s=d.subscribe(h),h(),!0},c=()=>{o=setTimeout(()=>{o=null,n+=1,!i(a)&&n<40&&c()},250)};return t(Cs()),i(r)||c(),{retry:l=>(l&&(a=l),i(a)),unsubscribe:()=>{o&&clearTimeout(o),o=null;try{typeof s=="function"&&s()}catch{}s=null}}};var pe="sensor.home_energy_advisor_devices",Ns="home_energy_advisor",me=r=>{if(r?.states?.[pe])return pe;let e=r?.entities;if(!e)return pe;for(let[t,s]of Object.entries(e))if(s?.platform===Ns&&Array.isArray(r?.states?.[t]?.attributes?.devices))return t;return pe},b=(r,e=void 0)=>{let t=r?.states?.[e??me(r)]?.attributes?.devices;return Array.isArray(t)?t.filter(s=>s?.key).map(Tt):[]},L=(r,e=void 0)=>{let t=r?.states?.[e??me(r)]?.attributes?.whole_home;return t?.key?Tt(t):null},At=(r,e=void 0)=>{let t=r?.states?.[e??me(r)]?.attributes?.settled_until;if(typeof t!="string")return null;let s=new Date(t);return Number.isNaN(s.getTime())?null:s},Ot=(r,e=void 0)=>{let t=r?.states?.[e??me(r)]?.attributes?.labels;return t&&typeof t=="object"?t:{}},Tt=r=>({key:r.key,name:r.name||r.key,deviceId:r.device_id??null,untracked:!!r.untracked,statistics:r.statistics??{},areaId:r.area_id??null,areaName:r.area_name??null,floorId:r.floor_id??null,floorName:r.floor_name??null,upstream:r.upstream??null,gross:!!r.gross,labels:Array.isArray(r.labels)?r.labels:[]});var $t=Object.freeze({kind:"all",id:null}),Ds={area:"areaId",floor:"floorId"},Re=new Map,Ie=r=>(Re.has(r)||Re.set(r,{filter:$t,listeners:new Set}),Re.get(r)),ee=r=>Ie(r).filter,fe=(r,e)=>{let{listeners:t}=Ie(r);return t.add(e),()=>t.delete(e)},Ct=(r,e)=>{let t=Ie(r),s={kind:e?.kind??"all",id:e?.id??null};if(!(s.kind===t.filter.kind&&s.id===t.filter.id)){t.filter=s;for(let o of t.listeners)try{o(s)}catch(n){console.warn("home-energy-advisor: a card could not follow the filter",n)}}},Ft=(r,e)=>{let{kind:t,id:s}=e??$t;if(t==="all")return!0;if(t==="device")return r.key===s;if(r.untracked)return!1;if(t==="label")return(r.labels??[]).includes(s);let o=Ds[t];return o?(r[o]??null)===s:!0};var Rt={day:"numeric",month:"short",year:"numeric"},U=r=>({language:r?.locale?.language||void 0,currency:r?.config?.currency||void 0,timeFormat:r?.locale?.time_format||void 0,timeZone:r?.locale?.time_zone==="server"?r?.config?.time_zone:void 0}),Ms=({timeFormat:r,language:e})=>{if(r==="language"||r==="system"||!r){let t=r==="system"?void 0:e;return new Date("January 1, 2023 22:00:00").toLocaleString(t).includes("10")}return r==="12"},Ne=(r,e)=>new Intl.DateTimeFormat(e.language,{hour:"numeric",minute:"2-digit",hourCycle:Ms(e)?"h12":"h23",timeZone:e.timeZone}).format(r),De=(r,e)=>`${new Intl.DateTimeFormat(e.language,{...Rt,timeZone:e.timeZone}).format(r)}, ${Ne(r,e)}`,Ls=(r,e)=>new Intl.DateTimeFormat(e.language,{weekday:"short",month:"short",day:"numeric",timeZone:e.timeZone}).format(r),Gs={hour:3600*1e3},It=(r,e,t)=>{let s=Gs[e];if(!s)return Ls(r,t);let o=new Date(r.getTime()+s);return`${Ne(r,t)} \u2013 ${Ne(o,t)}`},u=(r,{language:e,currency:t})=>typeof r!="number"||!Number.isFinite(r)?"-":new Intl.NumberFormat(e,{...Nt(t),signDisplay:"negative"}).format(r),Nt=r=>r?Me(r):{minimumFractionDigits:2,maximumFractionDigits:2},Me=r=>({style:"currency",currency:r,currencyDisplay:"narrowSymbol"}),Dt=(r,{language:e,currency:t}={})=>{let o=10**new Intl.NumberFormat(e,Nt(t)).resolvedOptions().maximumFractionDigits;return Math.round(r*o)/o},z=(r,{language:e,currency:t})=>{if(typeof r!="number"||!Number.isFinite(r))return"-";let s=t?{...Me(t),signDisplay:"exceptZero"}:{minimumFractionDigits:2,maximumFractionDigits:2,signDisplay:"exceptZero"};return new Intl.NumberFormat(e,s).format(r)},Hs=new Set(["actualCost","costAtGridPrice","energyUsed"]),Ps=new Set(["costSavings"]),x=(r,e)=>{if(typeof r!="number"||!Number.isFinite(r))return"";let t=Dt(r,e);return t===0?"":t>0?"gain":"loss"},js=new Set(["actualCost","costAtGridPrice","costSavings"]),K=(r,e,t)=>{if(typeof e!="number"||!Number.isFinite(e))return"";let s=js.has(r)?Dt(e,t):e;return s===0?"":Hs.has(r)?s<0?"gain":"loss":Ps.has(r)?s>0?"gain":"loss":""},Y=(r,e)=>{if(!Array.isArray(r))return"-";let[t,s]=r;if(![t,s].every(a=>Number.isFinite(a)))return"-";if(t===s)return u(t,e);let[o,n]=t<=s?[t,s]:[s,t];return`${u(o,e)} - ${u(n,e)}`},w=(r,{language:e})=>typeof r!="number"||!Number.isFinite(r)?"-":`${new Intl.NumberFormat(e,{maximumFractionDigits:1}).format(r)} kWh`,Mt={EUR:{symbol:"c",per:100},USD:{symbol:"\xA2",per:100},GBP:{symbol:"p",per:100}},te=(r,{language:e})=>typeof r!="number"||!Number.isFinite(r)?"-":new Intl.NumberFormat(e,{minimumFractionDigits:r===0?0:2,maximumFractionDigits:2}).format(r),re=({language:r,currency:e})=>e?Lt(r,e):"",Lt=(r,e)=>new Intl.NumberFormat(r,Me(e)).formatToParts(0).find(t=>t.type==="currency")?.value??"",_e=({language:r,currency:e})=>{if(!e)return"/kWh";let t=Mt[e];return`${t?t.symbol:Lt(r,e)}/kWh`},se=(r,{language:e,currency:t})=>{if(typeof r!="number"||!Number.isFinite(r))return"-";let s=t?Mt[t]:void 0;return new Intl.NumberFormat(e,{minimumFractionDigits:s?1:0,maximumFractionDigits:s?2:3}).format(s?r*s.per:r)},q=(r,{language:e})=>typeof r!="number"||!Number.isFinite(r)?"-":new Intl.NumberFormat(e,{style:"percent",maximumFractionDigits:0}).format(r),E=r=>String(r).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#39;"),oe=(r,{language:e})=>r?new Intl.DateTimeFormat(e,Rt).formatRange(r.start,r.end):"";var Ht="common",Pt="home_energy_advisor",Gt=`component.${Pt}.${Ht}.card_`,Ge=Object.freeze({paid:"Paid",would_have_paid:"Would have paid",saved:"Saved",lost:"Lost",range_column:"Paid (min-max)",range_note:"Paid (min-max) is the widest range these readings allow, not a typical error: a meter that reports every 30-90 minutes leaves the exact moment of use unknown.",range_whole_home:"What you paid could honestly sit between {range} - the widest these readings allow, not a typical error.",range_device:"What you paid could be between {range}.",range_note_rollover:"Hover over or tap a figure in Paid to see the range it could honestly have been. That range is the widest these readings allow, not a typical error: a meter that reports every 30-90 minutes leaves the exact moment of use unknown.",forgone_column:"Could have earned",forgone_note:"Could have earned is what the generation each device used could have earned had you exported it instead, at your export rate at the time. It is money you did not receive, not money you paid, and it is not part of Paid.",forgone_hidden_note:"Could have earned, what the generation each device used could have earned had you exported it instead, is shown on a wider screen.",device_costs_note:"The solid part of each bar is what the device cost. The whole bar is what it would have cost had all its energy come from the grid, at your grid price at the time.",compared:"{change} vs {before}",compared_period:"{period} vs {compared}",saved_share:"{percent} of what you would have paid was saved.",lost_share:"{percent} more was paid than the grid would have cost.",change:"Change",compared_series:"Earlier period",device:"Device",energy:"Energy",rate:"Rate",total:"Total",grid:"Grid",generation:"Generation",battery:"Battery",from_grid:"From the grid",from_generation:"From generation",from_battery:"From the battery",from_battery_grid:"From battery (grid)",of_which_stored_solar:"Of which stored solar",energy_used_came_from:"Where the {energy} of energy used came from",including_stored_solar:"including stored solar",energy_used:"Energy used",unaccounted:"Unaccounted",self_sufficiency_note:"Solar stored in the battery counts as your own. Battery energy charged from the grid does not, and is shown on its own.",household:"Household",generation_saved:"Generation saved",battery_saved:"Battery saved",exports_earned:"Exports earned",installation_note:"For the whole home: your own generation, your battery and your exports, measured against your current tariff. What the battery lost is taken off what it saved.",no_installation:"There is no generation or battery here, so nothing for an installation to have earned.",title_installation:"What your installation earned",title_plans:"Compare tariff plans",tab_summary:"Summary",tab_devices:"Devices",tab_tariffs:"Tariffs",plans_your_plan:"Current plan",plans_cheapest:"Cheapest",plans_energy:"Import cost",plans_export:"Export income",plans_daily:"Daily charges",plans_plan:"Plan",plans_prices:"Prices",plans_you_pay:"What you pay",plans_you_earn:"What you earn",plans_market_price:"Market price",plans_export_rate:"Export",plans_daily_rate:"Daily",plans_per_day:"{amount}/day",plans_total:"Total",plans_without:"Without solar or battery",plans_saves:"saves {amount}",plans_costs_more:"{amount} more",plans_vs_current:"vs current plan",plans_same_short:"The same",plans_flows:"Imported {imported} and exported {exported} in this period.",plans_breakdown_hidden:"Import cost, export income and daily charges are shown on a wider screen.",plans_incomplete:"Not every hour has a price, so it cannot be compared. Edit the plan to finish its bands.",plans_note:"For the whole home: each plan priced at the electricity you actually imported and exported, as if your battery had run the same way. Prices are compared as you entered them.",plans_no_readings:"Your grid meters recorded nothing in this period, so only the daily charges are shown.",plans_no_current:"Mark one plan as the one you are on to see how the others compare.",plans_no_price:"No market price was recorded in this period, so it cannot be compared.",plans_export_unpaid:"{amount} of export not paid: capped at each month's energy cost.",plans_export_carried:"{amount} of export carried forward and not yet used.",plans_compared_from_plan:"Compared from {date}, when {plan}'s prices start, so every plan covers the same days.",plans_compared_from_meters:"Compared from {date}, when your grid meters' readings start, so every plan covers the same days.",plans_carried:"{hours} h priced at the last market price, where none was recorded.",plans_market_hourly:"Market prices are applied hour by hour, at each hour's average.",plans_market_five_minutes:"Market prices are applied five minutes at a time.",plans_market_from:"Market prices are applied five minutes at a time from {date}, and hour by hour, at each hour's average, before that.",no_plans:"No tariff plans yet. Add one from the Home Energy Advisor integration, with Add tariff plan.",title_totals:"Cost summary",title_devices:"Cost by device",title_device_costs:"What each device cost",title_cost_over_time:"Cost over time",title_sources:"Where the energy came from",title_self_sufficiency:"Self-sufficiency",title_distribution:"Where the cost went",title_distribution_energy:"Where the energy went",no_devices:"No devices are being tracked yet.",no_devices_in_filter:"No tracked device matches what the page is showing.",title_filter:"Show",filter_everything:"Everything",filter_rooms:"Rooms",filter_floors:"Floors",filter_labels:"Labels",filter_devices:"Devices",filter_unfiled:"Not in one",device_untracked:"Untracked",hourly_shape_estimate:"One device's hourly shape is an estimate: each meter reading is spread across the hours it spanned, so cost may not land in the hour the energy was used.",still_accruing:"The last interval is still being counted, so its bar will grow. Figures are complete about twenty minutes behind the clock, which is how long meters are given to report.",statistics_failed:"Statistics could not be loaded.",loading:"Loading\u2026",no_picker:"Add an Energy date picker card to choose the range.",chart_not_loaded:"Home Assistant's chart component is not loaded. Adding any energy or statistics card to this dashboard will load it.",no_cost_in_period:"No cost recorded in this period.",no_energy_in_period:"No energy recorded in this period.",editor_title:"Title",editor_collection_key:"Energy period (collection key)",editor_devices:"Devices (all, if none are chosen)",editor_sort_by:"Order by",editor_layout:"Layout",editor_metric:"Measure by",editor_group_by_floor:"Group by floor",editor_group_by_area:"Group by area",editor_range:"Show the cost range as",editor_range_auto:"Automatic: a column where there is room",editor_range_rollover:"A rollover on Paid",editor_range_column:"Its own column"}),Le=new Map,jt=new Map,Bt=r=>r?.locale?.language||r?.language||"en",O=r=>{let e=Bt(r);return Le.has(e)||Le.set(e,Bs(r,e).then(t=>(jt.set(e,t),t))),Le.get(e)},Bs=async(r,e)=>{try{let{resources:t}=await r.callWS({type:"frontend/get_translations",language:e,category:Ht,integration:[Pt]});return Object.freeze({...Ge,...Ws(t)})}catch(t){return console.warn("home-energy-advisor: falling back to English labels",t),Ge}},k=r=>jt.get(Bt(r))??Ge,Ws=r=>Object.fromEntries(Object.entries(r??{}).filter(([e,t])=>e.startsWith(Gt)&&t).map(([e,t])=>[e.slice(Gt.length),t])),m=(r,e)=>Object.entries(e).reduce((t,[s,o])=>t.replaceAll(`{${s}}`,o),r);var S=Object.freeze({energyUsed:"energy_used",actualCost:"actual_cost",costAtGridPrice:"cost_at_grid_price",energyFromGrid:"energy_from_grid",energyFromGeneration:"energy_from_generation",energyFromBattery:"energy_from_battery",energyFromBatterySolar:"energy_from_battery_solar",forgoneExport:"forgone_export"}),D=Object.freeze({costFloor:"lowest_possible_cost",costCeiling:"highest_possible_cost"}),He=()=>Object.fromEntries(Object.keys(S).map(r=>[r,0])),Kt=1440*60*1e3,Yt={hour:3600*1e3,day:Kt},Us=2,V=(r,e)=>r?.statistics?.[e],ne=r=>S.costAtGridPrice in(r?.statistics??{}),qt=(r,e,t,s=!1)=>e==="costAtGridPrice"&&!ne(r)?V(r,S.actualCost):e==="energyFromGrid"&&s?V(r,S.energyUsed):V(r,t),zs=r=>[S.energyFromGrid,S.energyFromGeneration,S.energyFromBattery].some(e=>e in(r?.statistics??{})),Ks=r=>r.length>0&&!r.some(zs),ge=(r,e=[])=>{let t=b(r);return Ks(t.length?t:e)},Ys=(r,e)=>{let t=r.flatMap(s=>[...Object.values(S),...Object.values(D)].map(o=>V(s,o)).filter(Boolean));return!e?.statistics||r.length===0?t:[...t,...Object.values(D).map(s=>V(e,s)).filter(Boolean)]},Vt=(r,e)=>{if(!e)return r;let t=new Map(e.devices.map(s=>[s.key,s]));return{...r,totals:{...r.totals,before:e.totals},devices:r.devices.map(s=>({...s,before:t.get(s.key)})),seriesBefore:qs(e.series,r.period,e.period)}},qs=(r,e,t)=>{if(!r?.length)return;let s=e.start.getTime()-t.start.getTime();return r.map(o=>({...o,start:new Date(o.start.getTime()+s),actualStart:o.start}))},C=({start:r,end:e})=>e-r>Us*Kt?"day":"hour",Wt=(r,e,t)=>{if(e!=="day")return new Date(r.getTime()+t*Yt.hour);let s=new Date(r);return s.setDate(s.getDate()+t),s},Zt=(r,e)=>{if(!r.length||!e)return r;let t=C(e),s=new Map(r.map(a=>[a.start.getTime(),a])),o=r[0].start,n=[];for(let a=0;;a--){let i=Wt(o,t,a);if(i.getTime()<e.start.getTime())break;n.push(s.get(i.getTime())??Ut(i))}n.reverse();for(let a=1;;a++){let i=Wt(o,t,a);if(i.getTime()>=e.end.getTime())break;n.push(s.get(i.getTime())??Ut(i))}return n},Ut=r=>({...He(),start:r,costSavings:0,accruing:!1}),zt=new WeakMap,Vs=(r,e)=>{let t=r.connection??r,s=zt.get(t);s||(s=new Map,zt.set(t,s));let o=JSON.stringify(e),n=s.get(o);if(n)return n;let a=r.callWS(e).finally(()=>s.delete(o));return s.set(o,a),a},Pe=async(r,e,t,s,o=null)=>{let n=Ys(e,s),a=n.length?await Vs(r,{type:"recorder/statistics_during_period",start_time:t.start.toISOString(),end_time:t.end.toISOString(),statistic_ids:n,period:C(t),types:["change"]}):{},i=ge(r,e),c=Qs(e.map(l=>Xs(l,a,t,i)));return{period:t,gridOnly:i,devices:c,totals:eo(c),wholeHome:Xt(s,a,t),series:Zs(e,a,t,o,i)}},Xt=(r,e,t)=>{if(!r)return;let s={};for(let[o,n]of Object.entries(D)){let a=e?.[V(r,n)];if(!Array.isArray(a))return;s[o]=Jt(a,t)}return s},Zs=(r,e,t,s,o)=>{let n=new Map,a=new Set(r.filter(c=>c.gross).map(c=>c.key));for(let c of r.filter(l=>!a.has(l.upstream)))for(let[l,d]of Object.entries(S)){let h=e?.[qt(c,l,d,o)];for(let p of Qt(h,t)){let v=n.get(p.start)??He();v[l]+=p.change,n.set(p.start,v)}}let i=Yt[C(t)]??0;return[...n.entries()].sort(([c],[l])=>c-l).map(([c,l])=>({...l,start:new Date(c),costSavings:l.costAtGridPrice-l.actualCost,accruing:s?c+i>s.getTime():!1}))},Xs=(r,e,t,s)=>{let o=Object.fromEntries(Object.entries(S).map(([n,a])=>[n,Jt(e?.[qt(r,n,a,s)],t)]));return{...r,...o,...Xt(r,e,t),costSavings:o.costAtGridPrice-o.actualCost}},Qs=r=>{let e=new Map;for(let t of r)t.upstream&&e.set(t.upstream,[...e.get(t.upstream)??[],t]);return r.map(t=>{if(!t.gross)return t;let s={...t};for(let o of Object.keys(S)){let n=(e.get(t.key)??[]).reduce((a,i)=>a-i[o],t[o]);s[o]=Math.abs(n)<Js(o)?0:n}return s.costSavings=s.costAtGridPrice-s.actualCost,s})},Js=r=>r.startsWith("energy")?5e-4:.005,Qt=(r,{start:e,end:t})=>{if(!Array.isArray(r))return[];let s=[];for(let o of r){let n=new Date(o.start).getTime();n<e.getTime()||n>=t.getTime()||typeof o.change=="number"&&s.push({start:n,change:o.change})}return s},Jt=(r,e)=>Qt(r,e).reduce((t,s)=>t+s.change,0),eo=r=>({...r.reduce((t,s)=>{for(let o of Object.keys(t))t[o]+=s[o];return t},{...He(),costSavings:0}),...to(r)}),to=r=>{let e=Object.keys(D);return!r.length||!r.every(t=>e.every(s=>s in t))?{}:Object.fromEntries(e.map(t=>[t,r.reduce((s,o)=>s+o[t],0)]))};var ro=`
  :host {
    --hea-space-xs: 4px;
    --hea-space-s: 8px;
    --hea-space-m: 12px;
    --hea-space-l: 16px;
  }
  .body { padding: var(--hea-space-l); }
  .period {
    margin-top: var(--hea-space-l);
    color: var(--secondary-text-color);
    font-size: 0.9em;
  }
  .hint {
    margin-top: var(--hea-space-xs);
    color: var(--secondary-text-color);
    font-size: 0.8em;
  }
  .message { margin: 0; color: var(--secondary-text-color); }
  /* Home Assistant's own energy-graph chip, reproduced rather than used: that
     element is registered by their energy cards, so a dashboard carrying only
     ours may never have loaded it. */
  .chip {
    font-size: var(--ha-font-size-m, 14px);
    font-weight: var(--ha-font-weight-medium, 500);
    line-height: normal;
    white-space: nowrap;
    padding: var(--ha-space-1, 4px) var(--ha-space-2, 8px);
    border-radius: var(--ha-border-radius-md, 8px);
    border: 1px solid var(--divider-color);
  }
  .chip:empty { display: none; }
`,so=`
  .loss { color: var(--error-color, #db4437); }
  .gain { color: var(--success-color, #4caf50); }
`,I="(max-width: 767px)",T=class extends HTMLElement{static cardStyle="";static narrowQuery="";static titleKey="";_titleKey(){return this.constructor.titleKey}get _labels(){return k(this._hass)}constructor(){super(),this.attachShadow({mode:"open"}),this._state="loading",this._request=0}setConfig(e){if(e.devices!==void 0&&!Array.isArray(e.devices))throw new Error("`devices` must be a list of device keys");this._config=e,this._render()}set hass(e){this._hass=e,this._subscription?this._subscription.retry(e):this._subscribe(),this._refetchIfDevicesChanged()}connectedCallback(){this._render(),this._hass&&!this._subscription&&this._subscribe(),this._watchScreen()}disconnectedCallback(){this._subscription?.unsubscribe(),this._subscription=null,this._unfilter?.(),this._unfilter=null,this._screen?.removeEventListener?.("change",this._onScreenChange),this._screen=null}_watchScreen(){let{narrowQuery:e}=this.constructor;!e||this._screen||(this._screen=globalThis.matchMedia?.(e),this._onScreenChange??=()=>this._render(),this._screen?.addEventListener?.("change",this._onScreenChange))}_isNarrow(){return!!globalThis.matchMedia?.(I)?.matches}_subscribe(){this._subscription=St(this._hass,this._config?.collection_key,e=>{this._period=e,this._scheduleFetch()}),this._unfilter=fe(this._config?.collection_key,()=>this._scheduleFetch())}_scheduleFetch(){this._fetchPending||(this._fetchPending=!0,queueMicrotask(()=>{this._fetchPending=!1,this._fetch()}))}_refetchIfDevicesChanged(){let e=this._devices().map(t=>t.key).join(",");e!==this._deviceKeys&&(this._deviceKeys=e,this._period&&this._scheduleFetch())}_devices(){let e=b(this._hass),t=this._config?.devices,s=t?e.filter(n=>t.includes(n.key)):e,o=this._filter();return s.filter(n=>Ft(n,o))}_filter(){return ee(this._config?.collection_key)}_isFiltered(){return!!this._config?.devices||this._filter().kind!=="all"}async _fetch(){if(!this._hass||!this._period)return;let e=this._devices(),t=++this._request;if(await O(this._hass),e.length===0){this._state="empty",this._render();return}let s=this._isFiltered()?void 0:L(this._hass);try{let o=At(this._hass),[n,a]=await Promise.all([Pe(this._hass,e,this._period,s,o),this._period.compare?Pe(this._hass,e,this._period.compare,s):void 0]);if(t!==this._request)return;this._result=Vt(n,a),this._state="ready"}catch(o){if(t!==this._request)return;this._state="error",console.error(`${this.localName}: could not load statistics`,o)}this._render()}_render(){let e=U(this._hass);this.shadowRoot.innerHTML=`
      <style>${ro}${this.constructor.cardStyle}${so}</style>
      <ha-card>
        <div class="body" data-state="${this._state}">${this._content(e)}</div>
      </ha-card>
    `;let t=this._config?.title??this._labels[this._titleKey()];t&&this._writeHeader(t,e),this._afterRender()}_writeHeader(e,t){let s=this.shadowRoot.querySelector("ha-card"),o=this._headerChip(t);if(o===void 0){s.setAttribute("header",e);return}s.insertAdjacentHTML("afterbegin",`<div class="card-header" style="display: flex; justify-content: space-between;
         align-items: center; gap: var(--hea-space-s); padding-bottom: 0;">
        <span class="title">${E(e)}</span>
        <span class="chip">${E(o)}</span>
      </div>`)}_headerChip(){}_afterRender(){}_content(e){return this._state==="loading"?`<p class="message" role="status">${this._labels.loading}</p>`:this._state==="empty"?`<p class="message">${this._labels.no_devices}</p>`:this._state==="error"?`<p class="message">${this._labels.statistics_failed}</p>`:`${this._body(e)}${this._caption(e)}`}_caption(e){let t=this._period?.fallback?`<div class="hint">${this._labels.no_picker}</div>`:"";return`<div class="period">${this._periodLabel(e)}</div>${t}`}_periodLabel(e){let t=oe(this._period,e),s=this._period?.compare;return s?m(this._labels.compared_period,{period:t,compared:oe(s,e)}):t}},_=(r,e,{name:t,description:s})=>{customElements.get(r)||customElements.define(r,e),globalThis.customCards=globalThis.customCards??[],globalThis.customCards.some(o=>o.type===r)||globalThis.customCards.push({type:r,name:t,description:s})};var oo={title:"editor_title",collection_key:"editor_collection_key",devices:"editor_devices",sort_by:"editor_sort_by",layout:"editor_layout",metric:"editor_metric",group_by_floor:"editor_group_by_floor",group_by_area:"editor_group_by_area",range:"editor_range"},f=class extends HTMLElement{constructor(){super(),this.attachShadow({mode:"open"})}setConfig(e){this._config=e,this._render()}set hass(e){this._hass=e,this._render(),O(e).then(()=>this._render())}_extraSchema(){return[]}_render(){if(!this._config)return;let e=this.shadowRoot.querySelector("ha-form");e||(e=document.createElement("ha-form"),e.computeLabel=t=>k(this._hass)[oo[t.name]]??t.name,e.addEventListener("value-changed",t=>this._report(t.detail.value)),this.shadowRoot.append(e)),e.hass=this._hass,e.data=this._config,e.schema=this._schema()}_schema(){return[{name:"title",selector:{text:{}}},{name:"collection_key",selector:{text:{}}},{name:"devices",selector:{select:{multiple:!0,mode:"list",options:b(this._hass).map(e=>({value:e.key,label:e.name}))}}},...this._extraSchema()]}_report(e){this.dispatchEvent(new CustomEvent("config-changed",{detail:{config:no({...this._config,...e})},bubbles:!0,composed:!0}))}},no=r=>Object.fromEntries(Object.entries(r).filter(([,e])=>e!==""&&e!==void 0&&e!==null&&!(Array.isArray(e)&&e.length===0))),g=(r,e)=>{customElements.get(r)||customElements.define(r,e)};var F=class extends T{static chartTag="ha-chart-base";static bearingCard={type:"statistics-graph",entities:[]};static emptyKey="no_cost_in_period";static chartHeight="clamp(320px, 40vw, 480px)";static cardStyle=`
    ha-chart-base { display: block; --chart-max-height: none; }
  `;constructor(){super(),this._chartReady=!!customElements.get(this.constructor.chartTag)}getCardSize(){return 6}connectedCallback(){super.connectedCallback(),this._chartReady||this._loadChartComponent()}async _loadChartComponent(){let{chartTag:e,bearingCard:t}=this.constructor;customElements.whenDefined(e).then(()=>{this._chartReady=!0,this._render()});try{await(await globalThis.loadCardHelpers?.())?.createCardElement(t)}catch(s){console.warn(`${e}: could not be loaded`,s)}}_isEmpty(){return(this._result?.series??[]).length===0}_body(){return this._chartReady?this._isEmpty()?`<p class="message">${this._labels[this._emptyKey()]}</p>`:this._chartMarkup():`<p class="message">${this._labels.chart_not_loaded}</p>`}_emptyKey(){return this.constructor.emptyKey}_chartMarkup(){return'<ha-chart-base chart-type="bar"></ha-chart-base>'}_afterRender(){let e=this.shadowRoot.querySelector(this.constructor.chartTag);e&&(e.hass=this._hass,this._draw(e))}_chartHeight(){return this.constructor.chartHeight}_draw(e){e.height=this._chartHeight(),e.data=this._series(),e.options=this._options(this._chartLocale())}_chartLocale(){return U(this._hass)}_colour({variable:e,fallback:t}){return getComputedStyle(this).getPropertyValue(e).trim()||t}};var ao=/^#([\da-f]{3}|[\da-f]{6})$/i,io=/^rgba?\(([^)]+)\)$/i,je=r=>{let e=ao.exec(String(r).trim());if(e){let o=e[1];return(o.length===3?[...o].map(a=>a+a):[0,2,4].map(a=>o.slice(a,a+2))).map(a=>Number.parseInt(a,16))}let t=io.exec(String(r).trim());if(!t)return;let s=t[1].split(/[\s,/]+/).filter(Boolean).slice(0,3).map(Number);return s.length===3&&s.every(Number.isFinite)?s:void 0},N=(r,e)=>{let t=je(String(r).trim());return t?`rgba(${t.join(", ")}, ${e})`:r},co=([r,e,t])=>(.2126*r+.7152*e+.0722*t)/255,ye=r=>{let e=je(lo(r));return e?co(e)>.5:!1},lo=r=>{let e=[r,r?.ownerDocument?.documentElement].filter(Boolean);for(let t of e){let s=getComputedStyle(t),o=s.getPropertyValue("--primary-text-color").trim()||s.color;if(je(o))return o}return""};var er=Object.freeze({variable:"--primary-color",fallback:"#03a9f4"}),tr=Object.freeze({variable:"--success-color",fallback:"#4caf50"}),ho=Object.freeze({paid:"paid",would_have_paid:"would-have-paid",saved:"saved"}),be=`
  .swatch {
    display: inline-block;
    box-sizing: border-box;
    width: 0.62em;
    height: 0.62em;
    margin-right: 0.45em;
    border-radius: 2px;
  }
  .swatch.paid { background: var(--primary-color, #03a9f4); }
  .swatch.saved { background: var(--success-color, #4caf50); }
  .swatch.would-have-paid { border: 1.5px solid var(--primary-text-color, #212121); }
`,ve=r=>{let e=typeof r=="string"?ho[r]:void 0;return e?`<span class="swatch ${e}" aria-hidden="true"></span>`:""};var M=(r,e,t,{bold:s=!1}={})=>{let o=document.createElement("div");o.style.display="flex",o.style.justifyContent="space-between",o.style.gap="16px",s&&(o.style.fontWeight="bold");let n=document.createElement("span");n.textContent=r;let a=document.createElement("span");return a.textContent=e,a.style.fontVariantNumeric="tabular-nums",t&&(a.style.color=t),o.append(n,a),o},uo=r=>{let e=document.createElement("span");return e.style.display="inline-block",e.style.width="10px",e.style.height="10px",e.style.borderRadius="10px",e.style.marginInlineEnd="4px",e.style.verticalAlign="middle",e.style.backgroundColor=r,e},rr=(r,e,t,s)=>{let o=M(e,t,s);return o.firstChild.prepend(uo(r)),o},xe=r=>{let e=document.createElement("div");return e.textContent=r,e.style.fontWeight="bold",e.style.textAlign="center",e.style.marginBottom="4px",e},sr=r=>{let e=document.createElement("div");return e.textContent=r,e.style.marginTop="4px",e.style.maxWidth="260px",e.style.whiteSpace="normal",e.style.opacity="0.7",e};var ir="hea-cost-over-time-card",cr=`${ir}-editor`,po={hour:3600*1e3,day:1440*60*1e3},mo=50,fo=.5,_o=(r,e)=>{if(!r.length||!e)return 0;let t=po[C(e)]??0,s=r.length>=2?r[1].start.getTime()-r[0].start.getTime():void 0;return(s?Math.min(s,t):t)/2},G={paid:{id:"paid",name:"paid",...er},saved:{id:"saved",name:"saved",...tr}},lr={variable:"--error-color",fallback:"#db4437"},go={gain:{variable:"--success-color",fallback:"#4caf50"},loss:lr},Be=r=>r.value?.[1]??0,yo=r=>r.value?.[2],bo=.45,we={id:"before",name:"compared_series",variable:"--secondary-text-color",fallback:"#727272"},We=class extends F{static titleKey="title_cost_over_time";static getConfigElement(){return document.createElement(cr)}_series(){let e=Zt(this._result?.series??[],this._result?.period),t=this._colour(lr),s=this._labels,o=this._result?.seriesBefore,n=_o(e,this._result?.period),a={...ar(G.paid,this._colour(G.paid),s),data:e.map(c=>or(c,nr(c,c.actualCost,n)))},i={...ar(G.saved,this._colour(G.saved),s),data:e.map(c=>{let l=nr(c,c.costSavings,n),d=c.costSavings<0?dr(t):void 0;return or(c,l,d)})};return[...ue(this._result?.gridOnly?[a]:[a,i]),...o?.length?[{id:we.id,name:s[we.name],type:"line",symbol:"none",lineStyle:{type:"dashed",width:2},itemStyle:{color:this._colour(we)},data:o.map(c=>[c.start.getTime()+n,c.costAtGridPrice])}]:[]]}_caption(e){return`${super._caption(e)}${this._stillAccruingNote()}`+this._accrualNote()}_stillAccruingNote(){return(this._result?.series??[]).some(e=>e.accruing)?`<div class="hint">${this._labels.still_accruing}</div>`:""}_accrualNote(){return this._devices().length!==1||!this._period||C(this._period)!=="hour"?"":`<div class="hint">${this._labels.hourly_shape_estimate}</div>`}_tooltipFor(e,t){let s=(Array.isArray(e)?e:[e]).filter(c=>c.componentSubType==="bar"),o=s.filter(c=>Be(c)!==0);if(!o.length)return;let n=this._bucketAt(s.map(yo).find(c=>c!==void 0)),a=document.createElement("div");a.append(xe(this._spanOf(n,t)));for(let c of o)a.append(this._tooltipRowFor(c,t));let i=s.reduce((c,l)=>c+Be(l),0);return o.length>1&&a.append(M(this._labels.would_have_paid,u(i,t),void 0,{bold:!0})),n?.accruing&&a.append(sr(this._labels.still_accruing)),a}_tooltipRowFor(e,t){let s=Be(e),o=e.seriesId===G.saved.id?x(s,t):"",n=o==="loss"?this._labels.lost:e.seriesName;return rr(e.color,n,u(s,t),o?this._colour(go[o]):void 0)}_bucketAt(e){if(e!==void 0)return(this._result?.series??[]).find(t=>t.start.getTime()===e)}_spanOf(e,t){return!e||!this._period?"":It(e.start,C(this._period),t)}_headerChip(e){let t=this._result?.totals?.actualCost;return Number.isFinite(t)&&!this._isEmpty()?u(t,e):""}_axisBounds(){if(!this._period)return{};let{start:e,end:t}=this._period,s=new Date(t.getTime()-1);return C(this._period)==="hour"?s.setMinutes(30,0,0):(s.getHours()===0&&s.setHours(s.getHours()-1),s.setHours(0,0,0,0)),{min:e.getTime(),max:s.getTime()}}_options(e){let t=this._labels;return{xAxis:{type:"time",...this._axisBounds()},grid:{top:15,bottom:0,left:1,right:1,containLabel:!0},yAxis:{type:"value",name:re(e),nameGap:2,nameTextStyle:{align:"left"},boundaryGap:[0,0],splitNumber:5,splitLine:{show:!0},axisLabel:{formatter:s=>te(s,e),hideOverlap:!0}},tooltip:{trigger:"axis",axisPointer:{type:"shadow"},formatter:s=>this._tooltipFor(s,e)},legend:{show:!0,type:"custom",data:[G.paid,G.saved,...this._result?.seriesBefore?.length?[we]:[]].map(s=>({id:s.id,name:t[s.name],itemStyle:{color:this._colour(s)}}))}}}},or=(r,e,t=void 0)=>r.accruing?{value:e,itemStyle:{...t,opacity:bo}}:t?{value:e,itemStyle:t}:e,nr=(r,e,t)=>[r.start.getTime()+t,e,r.start.getTime()],ar=({id:r,name:e},t,s)=>({id:r,name:s[e],type:"bar",stack:"cost",barMaxWidth:mo,itemStyle:dr(t)}),dr=r=>({color:N(r,fo),borderColor:r,borderWidth:1}),Ue=class extends f{},vo=()=>{g(cr,Ue),_(ir,We,{name:"Home Energy Advisor: Cost over time",description:"What the period cost, stacked against what it would have cost at grid price."})};vo();var ae=(r,e)=>{let t=e?.statistics?.cost_savings;return!!(t&&r?.states?.[t])},hr=(r,e)=>({costSavings:r?.statistics?.cost_savings,batterySavings:r?.statistics?.battery_savings,lossesPaid:(e??[]).filter(t=>!t.untracked&&!t.upstream).filter(t=>!ne(t)).map(t=>t.statistics?.actual_cost).filter(Boolean)}),ur=(r,e)=>{let t=e?.cost_sensors??{},s=[];for(let o of r?.energy_sources??[]){if(o?.type!=="grid")continue;let n=Array.isArray(o.flow_to)?o.flow_to:[o];for(let a of n){let i=a?.stat_compensation||a?.stat_energy_to&&t[a.stat_energy_to];i&&!s.includes(i)&&s.push(i)}}return s},pr=r=>[r.costSavings,r.batterySavings,...r.lossesPaid??[],...r.exportsEarned??[]].filter(Boolean),mr=(r,e,t)=>{let s=p=>xo(r?.[p],t),o=s(e.costSavings),n=!!e.batterySavings,a=n?s(e.batterySavings):0,i=(e.lossesPaid??[]).reduce((p,v)=>p+s(v),0),c=e.exportsEarned??[],l=o-a,d=n?a-i:void 0,h=c.length?c.reduce((p,v)=>p+s(v),0):void 0;return{generationSaved:l,batterySaved:d,exportsEarned:h,total:l+(d??0)+(h??0)}},xo=(r,{start:e,end:t})=>{if(!Array.isArray(r))return 0;let s=0;for(let o of r){let n=new Date(o.start).getTime();n<e.getTime()||n>=t.getTime()||typeof o.change=="number"&&(s+=o.change)}return s};var Ve="hea",gr="Home Energy Advisor",wo="mdi:home-lightning-bolt",fr=`ll-strategy-dashboard-${Ve}`,_r=`ll-strategy-view-${Ve}`,A=4,yr=[{type:"custom:hea-totals-card"},{type:"custom:hea-devices-card",sort_by:"actual_cost"}],br=[{type:"custom:hea-cost-over-time-card"},{type:"custom:hea-sources-card",sort_by:"energy_used"}],Ke=[{type:"custom:hea-device-costs-card"},{type:"custom:hea-distribution-card"},{type:"custom:hea-self-sufficiency-card"}],vr={type:"custom:hea-installation-card"},Eo=new Set(["custom:hea-sources-card","custom:hea-self-sufficiency-card"]),Ee=(r,e)=>e?r.filter(t=>!Eo.has(t.type)):r,ko=r=>ae(r,L(r))?[...Ke,vr]:Ke,So=r=>({...r,grid_options:{columns:"full",rows:"auto"}}),$=(r,e)=>({type:"grid",column_span:e,cards:r.map(So)}),Ao=()=>({card:{type:"horizontal-stack",cards:[{type:"energy-date-selection",vertical_opening_direction:"up"},{type:"custom:hea-filter-card"}]},max_width:1600}),xr=r=>({type:"sections",max_columns:A,sections:[{type:"grid",cards:[{type:"markdown",content:k(r).no_devices}]}]}),wr={type:"custom:hea-plans-card"},Oo=async r=>{try{let e=await r.callWS({type:"home_energy_advisor/list_plans"});return Array.isArray(e?.plans)&&e.plans.length>0}catch{return!1}},Er=r=>({type:"sections",max_columns:A,sections:r.filter(e=>e.cards.length>0),footer:Ao()}),To=(r,e)=>{if(b(r).length===0)return xr(r);let t=ge(r);return Er([$(yr,A),$(Ee(br,t),A/2),$(Ee(ko(r),t),A/2),...e?[$([wr],A)]:[]])},[$o,Co]=yr,[Fo,Ro]=br,[Io,No,Do]=Ke,ze=(r,{path:e,titleKey:t,icon:s},o)=>({...Er(o),path:e,title:k(r)[t],icon:s}),Mo=(r,e)=>{if(b(r).length===0)return[xr(r)];let t=ge(r),s=ae(r,L(r))?[vr]:[],o=[ze(r,{path:"summary",titleKey:"tab_summary",icon:"mdi:view-dashboard"},[$([$o],A),$([Fo,...s],A/2),$(Ee([No,Do],t),A/2)]),ze(r,{path:"devices",titleKey:"tab_devices",icon:"mdi:format-list-bulleted"},[$([Co],A),$([Io],A/2),$(Ee([Ro],t),A/2)])];return e&&o.push(ze(r,{path:"tariffs",titleKey:"tab_tariffs",icon:"mdi:cash-multiple"},[$([wr],A)])),o},kr=async r=>{let[,e]=await Promise.all([O(r),Oo(r)]);return e},Ye=class extends HTMLElement{static async generate(e,t){return{views:Mo(t,await kr(t))}}static noEditor=!0;static getCreateSuggestions(){return{title:gr,icon:wo}}},qe=class extends HTMLElement{static async generate(e,t){return To(t,await kr(t))}},Lo=r=>{globalThis.customStrategies=globalThis.customStrategies??[],globalThis.customStrategies.some(e=>e.type===r.type)||globalThis.customStrategies.push(r)},Go=()=>{customElements.get(fr)||customElements.define(fr,Ye),customElements.get(_r)||customElements.define(_r,qe),Lo({type:Ve,strategyType:"dashboard",name:gr,description:"What each device cost to run, and what solar and the battery saved."})};Go();var Ze=Object.keys(S),Ho=Object.keys(D),Sr=r=>{let e=new Map;for(let t of r){if(!t.upstream)continue;let s=e.get(t.upstream);s?s.push(t):e.set(t.upstream,[t])}return e},Xe=(r,e)=>({...r,key:`${r.key}${Po}`,name:`${r.name} ${e.device_untracked}`,upstream:r.key,untracked:!1,gross:!1,residualOf:r.key}),Po="__untracked",Ar=(r,e)=>r.gross&&Ze.every(t=>!r[t])?[]:[Xe(r,e)],jo=r=>{let e=Object.fromEntries(Ze.map(t=>[t,0]));for(let t of r)for(let s of Ze)e[s]+=t[s]??0;for(let t of Ho)e[t]=r.every(s=>typeof s[t]=="number")?r.reduce((s,o)=>s+o[t],0):void 0;return e.costSavings=e.costAtGridPrice-e.actualCost,e},ke=(r,e)=>{let t=Sr(r);return t.size===0?r:r.flatMap(s=>t.has(s.key)?Ar(s,e):[s])},Or=(r,e,t=s=>s)=>{let s=Sr(r);if(s.size===0)return t(r).map(n=>({device:n,depth:0}));let o=(n,a)=>{if(!s.has(n.key))return[{device:n,depth:a}];let c=t([...s.get(n.key),...Ar(n,e)]).flatMap(d=>o(d,a+1)),l=c.filter(d=>!d.device.subtotal).map(d=>d.device);return[{device:{...n,...jo(l),subtotal:!0},depth:a},...c]};return t(r.filter(n=>!n.upstream)).flatMap(n=>o(n,0))};var R=Object.freeze(["#0072b2","#e69f00","#009e73","#cc79a7","#56b4e9","#d55e00","#8c6bb1","#3d9970"]),Bo=Object.freeze(["#4b46b3","#8d9b1f","#00a2ab","#b07ad2","#7fa0ee","#a8761b","#b26596","#5b8f3f"]),Qe=Object.freeze([R,Bo]),Wa=R.length*Qe.length,Z=Object.freeze({variable:"--secondary-text-color",fallback:"#8a8a8a"}),X=r=>{let e=(r??[]).filter(t=>!t.untracked).map(t=>t.key).sort(Wo);return new Map(e.map((t,s)=>{let o=Math.floor(s/R.length)%Qe.length;return[t,Qe[o][s%R.length]]}))},Wo=(r,e)=>r===e?0:r<e?-1:1;var Se=(r,e,t)=>{let s=r<0?e.lost_share:e.saved_share;return m(s,{percent:q(Math.abs(r),t)})},Uo=({costSavings:r,costAtGridPrice:e})=>{if(!(!Number.isFinite(r)||!Number.isFinite(e))&&!(e<=0))return r/e},ie=[{at:0,hue:3,light:48,dark:62},{at:.5,hue:35,light:46,dark:68},{at:1,hue:142,light:31,dark:76}],Tr={light:85,dark:70},zo=.7,$r=(r,e,t)=>r+(e-r)*t,Ko=.6,Yo=(r,e)=>{let t=ie.findIndex(i=>r<=i.at);if(t<=0)return{hue:ie[0].hue,lightness:ie[0][e]};let s=ie[t-1],o=ie[t],n=(r-s.at)/(o.at-s.at),a=t===1?n:n**Ko;return{hue:$r(s.hue,o.hue,a),lightness:$r(s[e],o[e],n)}},Cr=.05,H=r=>Math.round(r*10)/10,Ae=(r,{dark:e=!1}={})=>{let t=e?"dark":"light",s=n=>Math.max(0,n?.costAtGridPrice??0),o=Math.max(0,...(r??[]).map(s));return n=>{let a=Uo(n??{});if(a===void 0||o<=0)return;let i=Math.min(1,s(n)/o),c=i*(1+Cr)/(i+Cr),l=Math.min(1,Math.max(0,a)),{hue:d,lightness:h}=Yo(l,t),p=Tr[t]*c**zo;return{rate:a,text:`hsl(${H(d)}, ${H(p)}%, ${H(h)}%)`,edge:`hsla(${H(d)}, ${H(Tr[t])}%, ${H(h)}%, ${H(c)})`}}};var Lr="hea-device-costs-card",Gr=`${Lr}-editor`,Fr={variable:"--error-color",fallback:"#db4437"},qo={variable:"--secondary-text-color",fallback:"#727272"},Vo="earlier-period",Zo=["auto","vertical","horizontal"],Xo="paid",Je="saved",Rr="before",Qo=30,Jo=46,en=64,tn=240,rn=24,sn=12,on=2,nn=10,an=300,cn=120,ln="40vw",dn={left:8,right:16,top:8,bottom:28,containLabel:!0},Ir=1.5,Nr=.8,Dr=.45,Mr=.22,hn=/:(?:paid|saved|before)$/,un={gain:{variable:"--success-color",fallback:"#4caf50"},loss:{variable:"--error-color",fallback:"#db4437"}},pn=(r,e,t,s,o,n,a)=>{let i=document.createElement("div");if(i.append(xe(e),M(s.paid,u(r.actualCost,t))),!a){let d=x(r.costSavings,t);i.append(M(r.costSavings<0?s.lost:s.saved,u(r.costSavings,t),d?o(d):void 0),M(s.would_have_paid,u(r.costAtGridPrice,t)));let h=mn(n,t,s);h&&i.append(h)}let c=fn(r,t,s,o);c&&i.append(c);let l=_n(r,t,s);return l&&i.append(l),i},mn=(r,e,t)=>{if(!r)return;let s=document.createElement("div");return s.style.marginTop="4px",s.style.color=r.text,s.textContent=Se(r.rate,t,e),s},fn=(r,e,t,s)=>{let o=r.before?.actualCost;if(!Number.isFinite(o)||!Number.isFinite(r.actualCost))return;let n=r.actualCost-o,a=K("actualCost",n,e);return M(t.change,m(t.compared,{change:z(n,e),before:u(o,e)}),a?s(a):void 0)},_n=({costFloor:r,costCeiling:e},t,s)=>{if(![r,e].every(n=>Number.isFinite(n)))return;let o=document.createElement("div");return o.style.marginTop="4px",o.style.opacity="0.75",o.textContent=m(s.range_device,{range:Y([r,e],t)}),o},et=class extends F{static titleKey="title_device_costs";static narrowQuery=I;static getConfigElement(){return document.createElement(Gr)}_isEmpty(){return this._ranked().every(e=>!e.costAtGridPrice&&!e.actualCost)}_caption(e){let t=super._caption(e);return this._isEmpty()?t:`${t}<div class="hint">${this._labels.device_costs_note}</div>`}_ranked(){return ke(this._result?.devices??[],this._labels).sort((e,t)=>t.actualCost-e.actualCost||e.name.localeCompare(t.name))}_colourFor(e){if(e.untracked)return this._colour(Z);let t=e.residualOf??e.key;return this._colours().get(t)??R[0]}_colours(){return X(b(this._hass))}_verdicts(){return Ae(this._ranked(),{dark:ye(this)})}_sideways(){let e=this._config?.layout;return e==="horizontal"?!0:e==="vertical"?!1:this._isNarrow()}_comparing(){return this._ranked().some(e=>e.before)}_series(){let e=this._sideways()?this._sidewaysSeries():this._standingSeries();return ue(this._result?.gridOnly?e.filter(({id:t})=>t!==Je&&!t.endsWith(`:${Je}`)):e)}_sidewaysSeries(){let e=this._ranked(),t=this._colour(Fr),s=this._labels,o=n=>this._colourFor(n);return[{id:Xo,name:s.paid,type:"bar",stack:"cost",data:e.map(n=>({value:n.actualCost,itemStyle:{color:N(o(n),Nr)}}))},{id:Je,name:s.saved,type:"bar",stack:"cost",data:e.map(n=>{let a=n.costSavings<0?t:o(n);return{value:n.costSavings,itemStyle:{color:N(a,Mr),borderColor:a,borderWidth:Ir}}})},...this._comparing()?[{id:Rr,name:s.compared_series,type:"bar",stack:"earlier",data:e.map(n=>({value:n.before?n.before.actualCost:null,itemStyle:{color:N(o(n),Dr)}}))}]:[]]}_standingSeries(){let e=this._colour(Fr);return this._ranked().flatMap(t=>{let s=this._colourFor(t),o=t.costSavings<0?e:s,n=t.name;return[{id:`${t.key}:paid`,name:n,type:"bar",stack:t.key,itemStyle:{color:N(s,Nr)},data:[t.actualCost]},{id:`${t.key}:saved`,name:n,type:"bar",stack:t.key,itemStyle:{color:N(o,Mr),borderColor:o,borderWidth:Ir},data:[t.costSavings]},...t.before?[{id:`${t.key}:before`,name:n,type:"bar",stack:`${t.key}:before`,itemStyle:{color:N(s,Dr)},data:[t.before.actualCost]}]:[]]})}_tooltipFor({seriesId:e,dataIndex:t},s){let o=this._ranked(),n=this._sideways()?o[t]:o.find(a=>a.key===String(e??"").replace(hn,""));return n?pn(n,n.name,s,this._labels,a=>this._colour(un[a]),this._verdicts()(n),this._result?.gridOnly):void 0}_earlierKey(){if(!this._comparing())return[];let e=this._labels.compared_series,t={color:this._colour(qo)};return this._sideways()?[{id:Rr,name:e,itemStyle:t}]:[{id:Vo,secondaryIds:this._ranked().filter(s=>s.before).map(s=>`${s.key}:before`),name:e,itemStyle:t}]}_chartHeight(){if(this._sideways()){let t=this._ranked().length,s=this._comparing()?Jo:Qo;return`${Math.max(tn,en+t*s)}px`}let e=an+this._legendHeight();return`clamp(${e}px, ${ln}, ${e+cn}px)`}_legendHeight(){let e=Math.min(this._ranked().length,nn)+this._earlierKey().length;return Math.ceil(e/on)*rn+sn}_options(e){return this._sideways()?this._sidewaysOptions(e):this._standingOptions(e)}_sidewaysOptions(e){let t=this._earlierKey();return{xAxis:{type:"value",name:re(e),axisLabel:{formatter:s=>te(s,e),hideOverlap:!0}},yAxis:{type:"category",data:this._ranked().map(s=>s.name),inverse:!0},grid:dn,tooltip:{trigger:"item",formatter:s=>this._tooltipFor(s,e)},...t.length?{legend:{show:!0,type:"custom",data:t}}:{}}}_standingOptions(e){return{xAxis:{type:"category",data:[oe(this._period,e)]},yAxis:{type:"value",name:re(e),nameGap:2,nameTextStyle:{align:"left"},axisLabel:{formatter:t=>te(t,e),hideOverlap:!0}},tooltip:{trigger:"item",formatter:t=>this._tooltipFor(t,e)},legend:{show:!0,type:"custom",data:[...this._ranked().map(t=>({id:`${t.key}:paid`,secondaryIds:[`${t.key}:saved`,...t.before?[`${t.key}:before`]:[]],name:t.name,itemStyle:{color:this._colourFor(t)}})),...this._earlierKey()]}}}},tt=class extends f{_extraSchema(){return[{name:"layout",selector:{select:{mode:"dropdown",options:Zo}}}]}},gn=()=>{g(Gr,tt),_(Lr,et,{name:"Home Energy Advisor: Device costs (chart)",description:"What each device cost over the selected period, dearest first."})};gn();var st=`${be}
  /*
   * A table too wide for the card scrolls sideways - and said so nowhere, which
   * on a phone means the Saved and Rate columns simply do not exist as far as
   * the reader is concerned (HEA-103).
   *
   * Shadows at the edges, drawn only while there is something past them: the
   * two local-attachment gradients are painted in the content's own
   * coordinates and so slide away as it scrolls, uncovering the fixed shadows
   * beneath. Reaching the end hides that end's shadow, and a table that fits
   * shows neither - which is why this is CSS rather than a cue we would have
   * to remember to turn off.
   */
  .scroll {
    overflow-x: auto;
    background:
      linear-gradient(to right, var(--card-background-color, #fff), transparent) 0 0 / 32px 100% no-repeat local,
      linear-gradient(to left, var(--card-background-color, #fff), transparent) 100% 0 / 32px 100% no-repeat local,
      radial-gradient(farthest-side at 0 50%, rgba(0, 0, 0, 0.18), transparent) 0 0 / 12px 100% no-repeat scroll,
      radial-gradient(farthest-side at 100% 50%, rgba(0, 0, 0, 0.18), transparent) 100% 0 / 12px 100% no-repeat scroll;
  }
  /*
   * A figure carrying something extra, shown on hover, focus or tap (HEA-198).
   *
   * The focus rule is what makes it reachable at all on a touch screen and by
   * keyboard, so it is not decoration beside the hover one - it is the half that
   * works where most dashboards are read. The outline is left to the browser.
   *
   * Note for anyone editing this: a CSS comment here cannot quote a selector in
   * backticks, because this whole block is a template literal and a backtick
   * ends it. That mistake parsed as a syntax error in the module, not as CSS.
   */
  .reveal {
    position: relative;
    cursor: help;
    text-decoration: underline dotted
      var(--secondary-text-color, rgba(0, 0, 0, 0.54));
    text-underline-offset: 3px;
  }
  /*
   * Out of the layout entirely, which is the whole point: revealing this inline
   * widened the cell and reflowed the table, so every column jumped as the
   * pointer moved across it.
   *
   * It opens sideways and stays inside the row's own height. The table scrolls
   * horizontally, and setting one overflow axis to auto makes the other compute
   * to auto as well - so anything reaching above or below a row is clipped by
   * that container, however a tooltip would normally behave.
   */
  .revealed {
    display: none;
    position: absolute;
    right: 100%;
    top: 50%;
    transform: translateY(-50%);
    z-index: 2;
    margin-right: 8px;
    padding: 2px 8px;
    border-radius: 4px;
    white-space: nowrap;
    background: var(--card-background-color, #fff);
    box-shadow: 0 1px 6px rgba(0, 0, 0, 0.3);
    color: var(--secondary-text-color);
    font-size: 0.85em;
    font-weight: normal;
    font-variant-numeric: tabular-nums;
  }
  .reveal:hover .revealed,
  .reveal:focus .revealed,
  .reveal:focus-within .revealed {
    display: inline;
  }
  table { width: 100%; border-collapse: collapse; font-size: 0.95em; }
  th, td { padding: 6px 8px; text-align: right; white-space: nowrap; }
  th:first-child, td:first-child { text-align: left; white-space: normal; }
  /* Room for the verdict band, so it sits beside the name rather than under
     the first letter of it (HEA-106). On the head row, which carries no band,
     it keeps the heading aligned with the names beneath. */
  thead th:first-child, tbody th:first-child, tfoot th:first-child {
    padding-left: 14px;
  }
  /* A device that sits inside another one, indented under the row above it,
     one step further for each level it is nested (HEA-218). Added to the
     verdict band's own padding rather than replacing it, so the band stays
     where it is on every row and only the name moves (HEA-153). */
  tbody th.inside { padding-left: calc(14px + 16px * var(--depth, 1)); }
  /* A circuit's own meter, which contains the rows under it. Weighted like the
     totals line it behaves like, so a reader can see it is a subtotal and not
     another device competing with its own children. */
  tbody tr.subtotal th, tbody tr.subtotal td { font-weight: 500; }
  /* A figure that is not money anyone paid - the comparison, the money not
     received - read as context beside the figures that moved (ADR-0029). */
  td.muted { color: var(--secondary-text-color); }
  /*
   * A device name gets its own line on a phone. Wrapping it saves width the
   * table does not need - it already scrolls sideways - and spends height it
   * has none of: "Untracked Energy Devices" broke over three lines, making
   * every row 74px and the table 1461px on a 412px screen (HEA-103).
   */
  @media (max-width: 767px) {
    th:first-child, td:first-child { white-space: nowrap; }
  }
  thead th {
    color: var(--secondary-text-color);
    font-weight: 400;
    font-size: 0.85em;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    border-bottom: 1px solid var(--divider-color, #e0e0e0);
  }
  thead .unit { text-transform: none; letter-spacing: 0; }
  tbody td { border-bottom: 1px solid var(--divider-color, #e0e0e0); }
  tbody tr:last-child td { border-bottom: none; }
  tfoot th, tfoot td {
    font-weight: 500;
    border-top: 2px solid var(--divider-color, #e0e0e0);
  }
`,yn=(r,e,t,s)=>(r==="costSavings"?x(t,s):K(e,t,s))??"",rt=({classes:r=[],styles:e=[]})=>{let t=r.filter(Boolean),s=e.filter(Boolean);return(t.length?` class="${t.join(" ")}"`:"")+(s.length?` style="${s.join("; ")}"`:"")},Hr=r=>r?`box-shadow: inset ${bn} 0 0 ${r.edge}`:"",bn="4px",P=class extends T{static columns=[];static sorts={};static defaultSort="";static cardStyle=st;setConfig(e){let{sorts:t}=this.constructor;if(e.sort_by!==void 0&&!(e.sort_by in t))throw new Error(`\`sort_by\` must be one of: ${Object.keys(t).join(", ")}`);super.setConfig(e)}getCardSize(){return 3+Math.ceil((this._result?.devices.length??3)/2)}_columns(){return this.constructor.columns}_body(e){let t=this._columns(),s=this._verdictScale();return`
      <div class="scroll">
        <table>
          <thead><tr>${t.map(o=>this._heading(o,e)).join("")}</tr></thead>
          <tbody>${this._ranked().map(({device:o,depth:n})=>this._row(o,e,s,n)).join("")}</tbody>
          <tfoot>${this._total(e,s)}</tfoot>
        </table>
      </div>`}_verdictScale(){if(this._columns().some(e=>e.carriesVerdict))return Ae(this._result?.devices??[],{dark:ye(this)})}_heading({label:e},t){let s=this._labels;if(typeof e!="function")return`<th>${ve(e)}${s[e]}</th>`;let{text:o,unit:n}=e(t,s);return`<th>${o} <span class="unit">${E(n)}</span></th>`}_rank(e){let{sorts:t,defaultSort:s}=this.constructor,{field:o}=t[this._config?.sort_by??s];return[...e].sort((n,a)=>a[o]-n[o]||n.name.localeCompare(a.name))}_ranked(){return Or(this._result?.devices??[],this._labels,e=>this._rank(e))}_row(e,t,s,o){return`<tr${e.subtotal?' class="subtotal"':""}>${this._columns().map(a=>this._cell(a,e,t,s?.(e),o)).join("")}</tr>`}_cell(e,t,s,o,n){let{field:a,derive:i,format:c,reveal:l}=e;if(!c)return`<th scope="row"${rt({classes:[n?"inside":""],styles:[n?`--depth: ${n}`:"",Hr(o)]})}>${E(t.name)}</th>`;let d=i?i(t):t[a],h=this._revealed(c(d,s),l?.(t,s,this._labels));return`<td${this._figureAttributes(e,d,o,s)}>${h}</td>`}_figureAttributes({field:e,tone:t,muted:s,carriesVerdict:o},n,a,i){let c=o?this._verdictOn(a,i):null;return rt({classes:[yn(e,t,n,i),s?"muted":""],styles:[c?.style]})+(c?` title="${E(c.title)}"`:"")}_revealed(e,t){return t?`<span class="reveal" tabindex="0" aria-label="${E(t.label)}">${e}<span class="revealed" aria-hidden="true">${E(t.text)}</span></span>`:e}_total(e,t){let s=this._sumOfShown(),o=t?.(s);return`<tr>${this._columns().map(a=>{let{field:i,derive:c,format:l}=a;if(!l)return`<th scope="row"${rt({styles:[Hr(o)]})}>${this._labels.total}</th>`;let d=c?c(s):s[i];return`<td${this._figureAttributes(a,d,o,e)}>${l(d,e)}</td>`}).join("")}</tr>`}_verdictOn(e,t){return e?{style:`color: ${e.text}`,title:Se(e.rate,this._labels,t)}:null}_sumOfShown(){let e=[...new Set(this._columns().flatMap(({field:a,fields:i,derive:c,format:l})=>l?c?i??[]:a?[a]:[]:[]))],t=ke(this._result?.devices??[],this._labels),s=Object.fromEntries(this._columns().flatMap(({fields:a,field:i,readField:c})=>c?(a??[i]).map(l=>[l,c]):[])),o=a=>t.reduce((i,c)=>{for(let l of e){let d=a(c);i[l]+=s[l]?s[l](d,l):d[l]}return i},Object.fromEntries(e.map(i=>[i,0]))),n=o(a=>a);return t.length>0&&t.every(a=>a.before)&&(n.before=o(a=>a.before)),n}},Oe=(r,e)=>[{name:"sort_by",selector:{select:{mode:"dropdown",options:Object.entries(r).map(([t,{label:s}])=>({value:t,label:e[s]}))}}}];var jr="hea-devices-card",Br=`${jr}-editor`,vn=({actualCost:r,energyUsed:e})=>e>0?r/e:void 0,Wr=r=>Object.values(D).every(e=>e in(r.statistics??{})),Ur=r=>({field:r,fields:[r],derive:e=>!e.statistics||ne(e)?e[r]:void 0}),zr={...Ur("costAtGridPrice"),label:"would_have_paid",format:u,muted:!0},Kr={...Ur("costSavings"),label:"saved",format:u},ce={fields:["costFloor","costCeiling"],derive:({costFloor:r,costCeiling:e})=>[r,e],label:"range_column",format:Y,readField:(r,e)=>Number.isFinite(r[e])?r[e]:r.actualCost},Yr={fields:["actualCost"],derive:({actualCost:r,before:e})=>e&&Number.isFinite(r)&&Number.isFinite(e.actualCost)?r-e.actualCost:void 0,label:"change",format:z,tone:"actualCost"},Te={field:"actualCost",label:"paid",format:u,carriesVerdict:!0,reveal:(r,e)=>{if(!Wr(r)||!ce.fields.every(s=>Number.isFinite(r[s])))return null;let t=Y(ce.derive(r),e);return{text:t,label:`${u(r.actualCost,e)} (${t})`}}},qr={field:"forgoneExport",label:"forgone_column",format:u,muted:!0},Pr=[{field:"name",label:"device"},{field:"energyUsed",label:"energy",format:w},Te,Yr,ce,zr,Kr,qr,{derive:vn,label:(r,e)=>({text:e.rate,unit:_e(r)}),format:se}],Vr={actual_cost:{field:"actualCost",label:"paid"},cost_at_grid_price:{field:"costAtGridPrice",label:"would_have_paid"},cost_savings:{field:"costSavings",label:"saved"},energy_used:{field:"energyUsed",label:"energy_used"}},ot=class extends P{static titleKey="title_devices";static columns=Pr;static sorts=Vr;static defaultSort="actual_cost";static narrowQuery=I;static cardStyle=`${P.cardStyle}
    .disclosure {
      margin-top: var(--hea-space-m);
      color: var(--secondary-text-color);
      font-size: 0.8em;
    }
  `;static getConfigElement(){return document.createElement(Br)}_columns(){let e=this._rangeAsColumn(),t=new Set;e||t.add(ce),this._showsForgone()||t.add(qr),this._hasComparison()||t.add(Yr);let s=!!this._result?.gridOnly;return s&&(t.add(zr),t.add(Kr)),Pr.filter(o=>!t.has(o)).map(o=>{if(o!==Te)return o;let n=e?{...Te,reveal:void 0}:Te;return s?{...n,carriesVerdict:!1}:n})}_rangeAsColumn(){let e=this._config?.range;return(e==="column"||e!=="rollover"&&!this._isNarrow())&&this._hasEveryBound()}_showsForgone(){return this._hasForgone()&&!this._isNarrow()}_hasComparison(){return(this._result?.devices??[]).some(e=>e.before)}_hasForgone(){return(this._result?.devices??[]).some(e=>(e.forgoneExport??0)>0)}_hasEveryBound(){let e=(this._result?.devices??[]).filter(Wr);return e.length>0&&e.every(t=>ce.fields.every(s=>Number.isFinite(t[s])))}_body(e){return`${super._body(e)}${this._disclosure(e)}`}_disclosure(e){let t=[this._rangeDisclosure(e),this._forgoneNote()].filter(Boolean);return t.length?`<div class="disclosure">${t.join(" ")}</div>`:""}_forgoneNote(){return this._hasForgone()?this._showsForgone()?this._labels.forgone_note:this._labels.forgone_hidden_note:""}_rangeDisclosure(e){if(this._hasEveryBound())return this._rangeNote();let t=this._result?.wholeHome;if(!t)return"";let s=Y([t.costFloor,t.costCeiling],e);return m(this._labels.range_whole_home,{range:s})}_rangeNote(){return this._rangeAsColumn()?this._labels.range_note:this._labels.range_note_rollover}},nt=class extends f{_extraSchema(){let e=k(this._hass);return[...Oe(Vr,e),{name:"range",selector:{select:{mode:"dropdown",options:[{value:"auto",label:e.editor_range_auto},{value:"rollover",label:e.editor_range_rollover},{value:"column",label:e.editor_range_column}]}}}]}},xn=()=>{g(Br,nt),_(jr,ot,{name:"Home Energy Advisor: Devices",description:"Every tracked device over the selected period, ordered by what it cost."})};xn();var le="household",Q=Object.freeze({source:0,household:1,floor:2,area:3,device:4}),Zr=Object.freeze({cost:{field:"actualCost",sources:null},energy:{field:"energyUsed",sources:[{id:"grid",field:"energyFromGrid",variable:"--energy-grid-consumption-color",fallback:"#488fc2"},{id:"generation",field:"energyFromGeneration",variable:"--energy-solar-color",fallback:"#ff9800"},{id:"battery",field:"energyFromBattery",variable:"--energy-battery-out-color",fallback:"#4db6ac"}]}}),wn=r=>{let e=X(r);return t=>t.untracked?Z.fallback:e.get(t.key)??R[0]},En=({fallback:r})=>r,es=(r,e,{metric:t="cost",colour:s=En,deviceColour:o=wn(r),groupByFloor:n=!0,groupByArea:a=!0}={})=>{let{field:i,sources:c}=Zr[t]??Zr.cost,l=kn(r,i).filter(y=>y.value>0);if(l.length===0)return{nodes:[],links:[]};let d=l.reduce((y,he)=>y+he.value,0),h=An(l,{groupByFloor:n,groupByArea:a}),p=On(l,e,o),v=Tn(c,r.filter(y=>y[i]>0),e,s);return{nodes:[...v,{id:le,label:e.household,value:d,index:Q.household},...h.nodes,...p.nodes],links:[...v.map(y=>({source:y.id,target:le,value:y.value})),...h.links,...p.links]}},kn=(r,e)=>{let t=new Map(r.map(a=>[a.key,a])),s=new Map,o=[];for(let a of r){let i=Sn(a,t);i?s.has(i.key)?s.get(i.key).push(a):s.set(i.key,[a]):o.push(a)}let n=a=>{let i=Math.max(a[e]??0,0),c=(s.get(a.key)??[]).map(n).filter(l=>l.value>0);return{device:a,own:i,inside:c,value:c.reduce((l,d)=>l+d.value,i)}};return o.map(n)},Sn=(r,e)=>{let t=e.get(r.upstream);if(!t)return null;let s=new Set;for(let o=t;o;o=e.get(o.upstream)){if(o.key===r.key)return null;if(s.has(o.key))break;s.add(o.key)}return t},An=(r,{groupByFloor:e,groupByArea:t})=>{let s=new Map,o=new Map,n=[];return r.forEach(({device:a,value:i})=>{let c=e&&a.floorId?Xr(s,a.floorId,a.floorName):null,l=t&&a.areaId?Xr(o,a.areaId,a.areaName):null;c&&(c.value+=i),l&&(l.value+=i,l.floorId??=c?.id??null),n.push({source:$n(l,c),target:j(a),value:i})}),{nodes:[...Jr(s,"floor_",Q.floor),...Jr(o,"area_",Q.area)],links:[...Cn(s,o),...n]}},On=(r,e,t)=>{let s=Q.device+ts(r),o=[],n=[],a=(i,c)=>{let{device:l,own:d,inside:h,value:p}=i,v=h.length>0;if(o.push({id:j(l),label:l.name,value:p,index:v?Q.device+c:s,color:t(l),...Qr(l)}),!!v&&(h.forEach(y=>{n.push({source:j(l),target:j(y.device),value:y.value}),a(y,c+1)}),d>0)){let y=Xe(l,e);o.push({id:j(y),label:y.name,value:d,index:s,color:t(l),...Qr(l)}),n.push({source:j(l),target:j(y),value:d})}};return r.forEach(i=>a(i,0)),{nodes:o,links:n}},ts=r=>r.reduce((e,t)=>t.inside.length>0?Math.max(e,1+ts(t.inside)):e,0),j=r=>`device_${r.key}`,Tn=(r,e,t,s)=>(r??[]).map(o=>({id:`source_${o.id}`,label:t[o.id],value:e.reduce((n,a)=>n+(a[o.field]??0),0),index:Q.source,color:s(o)})).filter(o=>o.value>0),Xr=(r,e,t)=>(r.has(e)||r.set(e,{id:e,name:t||e,value:0}),r.get(e)),$n=(r,e)=>r?`area_${r.id}`:e?`floor_${e.id}`:le,Qr=r=>{let e=r.statistics?.actual_cost;return e?{entityId:e}:{}},Jr=(r,e,t)=>[...r.values()].map(s=>({id:`${e}${s.id}`,label:s.name,value:s.value,index:t})),Cn=(r,e)=>[...[...r.values()].map(t=>({source:le,target:`floor_${t.id}`,value:t.value})),...[...e.values()].map(t=>({source:t.floorId?`floor_${t.floorId}`:le,target:`area_${t.id}`,value:t.value}))];var rs="hea-distribution-card",ss=`${rs}-editor`,de={cost:{titleKey:"title_distribution",emptyKey:"no_cost_in_period",format:u},energy:{titleKey:"title_distribution_energy",emptyKey:"no_energy_in_period",format:w}},Fn="400px",Rn=88,In=240,Nn=["auto","horizontal","vertical"],at=Object.freeze({group_by_floor:!0,group_by_area:!0}),it=class extends F{static titleKey="title_distribution";static chartTag="ha-sankey-chart";static bearingCard={type:"energy-sankey"};static narrowQuery=I;static cardStyle=`
    ha-sankey-chart { display: block; min-height: 240px; }
  `;static getConfigElement(){return document.createElement(ss)}_isEmpty(){return this._layout().nodes.length===0}_verticalHeight({nodes:e}){let t=new Set(e.map(s=>s.index)).size;return`${Math.max(In,t*Rn)}px`}_metric(){return de[this._config?.metric]?this._config.metric:"cost"}_titleKey(){return de[this._metric()].titleKey}_emptyKey(){return de[this._metric()].emptyKey}_layout(){let e=X(b(this._hass));return es(this._result?.devices??[],this._labels,{metric:this._metric(),groupByFloor:this._config?.group_by_floor??at.group_by_floor,groupByArea:this._config?.group_by_area??at.group_by_area,colour:t=>this._colour(t),deviceColour:t=>t.untracked?this._colour(Z):e.get(t.key)??R[0]})}_chartMarkup(){return"<ha-sankey-chart></ha-sankey-chart>"}_draw(e){e.data=this._layout(),e.vertical=this._isVertical(),e.style.height=this._isVertical()?this._verticalHeight(e.data):Fn;let t=this._chartLocale(),{format:s}=de[this._metric()];e.valueFormatter=o=>s(o,t),this.toggleAttribute("data-vertical",e.vertical)}_isVertical(){let e=this._config?.layout;return e==="vertical"?!0:e==="horizontal"?!1:this._isNarrow()}},ct=class extends f{_extraSchema(){return[{name:"metric",selector:{select:{mode:"dropdown",options:Object.keys(de)}}},{name:"layout",selector:{select:{mode:"dropdown",options:Nn}}},{name:"group_by_floor",selector:{boolean:{}}},{name:"group_by_area",selector:{boolean:{}}}]}setConfig(e){super.setConfig({...at,...e})}},Dn=()=>{g(ss,ct),_(rs,it,{name:"Home Energy Advisor: Cost distribution",description:"Where the period's cost went, by floor, room, circuit and device."})};Dn();var os="hea-filter-card",ns=`${os}-editor`,Mn=[{kind:"area",label:"filter_rooms",id:"areaId",name:"areaName"},{kind:"floor",label:"filter_floors",id:"floorId",name:"floorName"}],B=({kind:r,id:e})=>`${r}:${e??""}`,Ln=r=>{let[e,t]=[r.slice(0,r.indexOf(":")),r.slice(r.indexOf(":")+1)];return{kind:e,id:t===""?null:t}},lt=class extends HTMLElement{constructor(){super(),this.attachShadow({mode:"open"})}setConfig(e){this._config=e,this._render()}set hass(e){this._hass=e,O(e).then(()=>this._renderIfChanged()),this._renderIfChanged()}getCardSize(){return 1}static getConfigElement(){return document.createElement(ns)}connectedCallback(){this._render(),this._unfilter??=fe(this._config?.collection_key,()=>this._renderIfChanged())}_signature(){return JSON.stringify([this._allDevices().map(e=>[e.key,e.name,e.areaId,e.areaName,e.floorId,e.floorName,e.labels]),B(ee(this._config?.collection_key)),this._labels.filter_rooms])}_renderIfChanged(){this._signature()!==this._drawn&&this._render()}disconnectedCallback(){this._unfilter?.(),this._unfilter=null}get _labels(){return k(this._hass)}_devices(){return b(this._hass).filter(e=>!e.untracked)}_allDevices(){return b(this._hass)}_optionsFor({kind:e,id:t,name:s},o){let n=new Map,a=!1;for(let c of o)c[t]?n.set(c[t],c[s]??c[t]):a=!0;let i=[...n.entries()].map(([c,l])=>({value:B({kind:e,id:c}),text:l})).sort((c,l)=>c.text.localeCompare(l.text));return a&&i.push({value:B({kind:e,id:null}),text:this._labels.filter_unfiled}),i}_labelOptions(e){let t=Ot(this._hass);return[...new Set(e.flatMap(o=>o.labels??[]))].map(o=>({value:B({kind:"label",id:o}),text:t[o]??o})).sort((o,n)=>o.text.localeCompare(n.text))}_deviceOptions(){return this._allDevices().map(e=>({value:B({kind:"device",id:e.key}),text:e.name})).sort((e,t)=>e.text.localeCompare(t.text))}_groups(){let e=this._devices(),t=Mn.map(o=>({label:this._labels[o.label],options:this._optionsFor(o,e)})),s=this._labelOptions(e);return s.length&&t.push({label:this._labels.filter_labels,options:s}),t.push({label:this._labels.filter_devices,options:this._deviceOptions()}),t.filter(o=>o.options.length>0)}_render(){let e=this._labels,t=this._devices();this._drawn=this._signature();let s=t.length?this._control(e):`<p class="message">${e.no_devices}</p>`;this.shadowRoot.innerHTML=`
      <style>
        /*
         * Matching Home Assistant's own energy-date-selection card, which this
         * is meant to stand beside: it fills its grid cell and centres its one
         * row, so a card of a different height next to it leaves the two
         * controls sitting on different lines (HEA-95).
         */
        ha-card {
          height: 100%;
          display: flex;
          flex-direction: column;
          justify-content: center;
        }
        /*
         * 4px of vertical padding around a 48px row, which is exactly the
         * energy-date-selection card beside it: 56px overall.
         *
         * Height is not cosmetic here. A horizontal stack stretches its cards
         * to the tallest of them, so a taller filter card raises the whole
         * footer and pushes the period picker's trigger down with it. Home
         * Assistant decides which way that picker's calendar opens by measuring
         * whether it fits above, and at a 639px viewport the margin is two
         * pixels - so 16px of padding here was enough to make the calendar open
         * downwards off the screen (HEA-115).
         */
        .body {
          box-sizing: border-box;
          min-height: 56px;
          padding: 4px 16px;
          display: flex;
          align-items: center;
          gap: 12px;
        }
        .label {
          color: var(--secondary-text-color);
          font-size: 0.85em;
          text-transform: uppercase;
          letter-spacing: 0.04em;
        }
        select {
          flex: 1 1 auto;
          min-width: 0;
          padding: 8px;
          color: var(--primary-text-color);
          background: var(--card-background-color, transparent);
          border: 1px solid var(--divider-color, #e0e0e0);
          border-radius: var(--ha-border-radius-small, 4px);
          font: inherit;
        }
        .message { margin: 0; padding: 16px; color: var(--secondary-text-color); }
      </style>
      <ha-card>${s}</ha-card>
    `;let o=this.shadowRoot.querySelector("select");o&&(o.value=B(ee(this._config?.collection_key)),o.addEventListener("change",()=>Ct(this._config?.collection_key,Ln(o.value))))}_control(e){let t=this._groups().map(s=>`<optgroup label="${E(s.label)}">${s.options.map(o=>`<option value="${E(o.value)}">${E(o.text)}</option>`).join("")}</optgroup>`).join("");return`<div class="body">
      <span class="label">${e.title_filter}</span>
      <select>
        <option value="${B({kind:"all",id:null})}">${E(e.filter_everything)}</option>
        ${t}
      </select>
    </div>`}},dt=class extends f{},Gn=()=>{g(ns,dt),_(os,lt,{name:"Home Energy Advisor: Filter",description:"Narrow every Home Energy Advisor card on the page to a room, a floor, a label or one device."})};Gn();var as="hea-installation-card",is=`${as}-editor`,Hn=[{key:"generationSaved",label:"generation_saved"},{key:"batterySaved",label:"battery_saved"},{key:"exportsEarned",label:"exports_earned"}],ht=class extends T{static titleKey="title_installation";static cardStyle=`
    .parts { display: flex; flex-direction: column; gap: var(--hea-space-s); }
    .part, .total {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: var(--hea-space-m);
    }
    .label { color: var(--secondary-text-color); }
    .value { color: var(--primary-text-color); white-space: nowrap; }
    .total {
      margin-top: var(--hea-space-s);
      padding-top: var(--hea-space-s);
      border-top: 1px solid var(--divider-color);
      font-weight: 500;
    }
    .total .value { font-size: 1.4em; }
  `;static getConfigElement(){return document.createElement(is)}getCardSize(){return 4}async _fetch(){if(!this._hass||!this._period)return;let e=++this._request;await O(this._hass);let t=L(this._hass);if(!ae(this._hass,t)){this._state="empty",this._render();return}try{let s={...hr(t,b(this._hass)),exportsEarned:await this._exportStatistics()},o=await this._hass.callWS({type:"recorder/statistics_during_period",start_time:this._period.start.toISOString(),end_time:this._period.end.toISOString(),statistic_ids:pr(s),period:C(this._period),types:["change"]});if(e!==this._request)return;this._earned=mr(o,s,this._period),this._state="ready"}catch(s){if(e!==this._request)return;this._state="error",console.error(`${this.localName}: could not load statistics`,s)}this._render()}async _exportStatistics(){try{let[e,t]=await Promise.all([this._hass.callWS({type:"energy/get_prefs"}),this._hass.callWS({type:"energy/info"})]);return ur(e,t)}catch{return[]}}_content(e){return this._state==="empty"?`<p class="message">${this._labels.no_installation}</p>`:super._content(e)}_body(e){let t=this._earned;return`
      <div class="parts">
        ${Hn.filter(({key:o})=>t?.[o]!==void 0).map(({key:o,label:n})=>this._line("part",o,this._labels[n],e)).join("")}
        ${this._line("total","total",this._labels.total,e)}
      </div>
      <div class="hint">${this._labels.installation_note}</div>`}_line(e,t,s,o){let n=this._earned?.[t],a=x(n,o);return`
      <div class="${e}">
        <span class="label">${s}</span>
        <span class="value${a?` ${a}`:""}" data-figure="${t}">${u(n,o)}</span>
      </div>`}},ut=class extends f{},Pn=()=>{g(is,ut),_(as,ht,{name:"Home Energy Advisor: What your installation earned",description:"What your generation, battery and exports earned over the selected period, for the whole home."})};Pn();var ls="hea-plans-card",ds=`${ls}-editor`,jn="home_energy_advisor/compare_plans",cs=[{key:"energy",label:"plans_energy",group:"pay"},{key:"daily",label:"plans_daily",figure:"daily_charges",group:"pay"},{key:"export",label:"plans_export",figure:"export_credit",group:"earn"}],Bn=[{key:"pay",label:"plans_you_pay"},{key:"earn",label:"plans_you_earn"}],J=r=>!!(r.incomplete||r.no_price),Wn=r=>"carried_hours"in r,Un=(r,e)=>J(r)||J(e)?(J(r)?1:0)-(J(e)?1:0):r.total-e.total,ft=class extends T{static titleKey="title_plans";static narrowQuery=I;static cardStyle=`${st}
    .flows {
      margin-bottom: var(--hea-space-m);
      color: var(--secondary-text-color);
      font-size: 0.9em;
    }
    /* As wide as the figures, not the card: spread across a full-width tab, a
       plan's figures sat too far apart to read across (HEA-280). The wrapper
       hugs the table too, so its scroll shadows sit at the table's own edges. */
    .scroll { width: fit-content; max-width: 100%; }
    /* A table that reads as one: bordered, its head shaded, a rule wherever a
       group of columns starts, so the figures never run into the notes below. */
    .plans {
      width: auto;
      font-variant-numeric: tabular-nums;
      border: 1px solid var(--divider-color, #e0e0e0);
    }
    .plans th, .plans td { padding-inline: 12px; }
    /* Heads in the main text colour and a heavier weight, so the table's shape
       reads at a glance (HEA-296). */
    .plans thead th {
      background: var(--secondary-background-color);
      color: var(--primary-text-color);
      font-weight: 500;
    }
    .plans thead tr.groups th { border-bottom: none; text-align: center; }
    .plans .rule { border-left: 1px solid var(--divider-color, #e0e0e0); }
    .plans .earn {
      background: color-mix(in srgb, var(--success-color, #4caf50) 9%, transparent);
    }
    .plans thead .earn {
      background: color-mix(
        in srgb,
        var(--success-color, #4caf50) 9%,
        var(--secondary-background-color)
      );
    }
    th.prices { text-align: left; }
    td.prices {
      text-align: left;
      color: var(--secondary-text-color);
      font-size: 0.85em;
      line-height: 1.6;
    }
    td.prices .rate { color: var(--primary-text-color); }
    .plans tbody td, .plans tbody th { border-bottom: none; vertical-align: top; }
    .plans tbody + tbody tr:first-child > * {
      border-top: 1px solid var(--divider-color, #e0e0e0);
    }
    .plans tbody th { font-weight: 500; color: var(--primary-text-color); }
    .tags { display: block; margin-top: 2px; font-weight: normal; }
    .tag {
      display: inline-block;
      margin-inline-end: var(--hea-space-s);
      padding: 0 var(--hea-space-s);
      border-radius: var(--ha-border-radius-pill, 9px);
      background: var(--secondary-background-color);
      color: var(--secondary-text-color);
      font-size: 0.8em;
    }
    /* Each badge in a colour of its own, so a plan's standing stands out:
       the theme's own colours, so a dark theme reads too (HEA-296). */
    .tag.current {
      background: color-mix(in srgb, var(--primary-color, #03a9f4) 18%, transparent);
      color: var(--primary-color, #03a9f4);
    }
    .tag.cheapest {
      background: color-mix(in srgb, var(--success-color, #4caf50) 18%, transparent);
      color: var(--success-color, #4caf50);
    }
    td.total { font-weight: 500; }
    .saves { font-size: 0.85em; }
    .saves:not(.gain):not(.loss) { color: var(--secondary-text-color); }
    tr.note td {
      padding-top: 0;
      padding-left: 14px;
      text-align: left;
      white-space: normal;
      color: var(--secondary-text-color);
      font-size: 0.85em;
    }
    td.incomplete {
      text-align: left;
      white-space: normal;
      color: var(--secondary-text-color);
    }
  `;static getConfigElement(){return document.createElement(ds)}getCardSize(){return 5}async _fetch(){if(!this._hass||!this._period)return;let e=++this._request;await O(this._hass);try{let t=await this._hass.callWS({type:jn,start_time:this._period.start.toISOString(),end_time:this._period.end.toISOString()});if(e!==this._request)return;this._compared=t,this._state=t?.plans?.length?"ready":"empty"}catch(t){if(e!==this._request)return;this._state="error",console.error(`${this.localName}: could not compare the plans`,t)}this._render()}_content(e){return this._state==="empty"?`<p class="message">${this._labels.no_plans}</p>`:super._content(e)}_body(e){if(!this._compared?.plans)return"";let t=[...this._compared.plans].sort(Un),s=t.filter(h=>!J(h)),o=s.find(h=>h.current),n=s.length>1?s[0]:void 0,a=!this._isNarrow(),i=a?cs:[],c=[this._compared.hours===0?this._labels.plans_no_readings:"",o?"":this._labels.plans_no_current,this._labels.plans_note,a?"":this._labels.plans_breakdown_hidden,s.some(Wn)?this._resolution(e):""].filter(Boolean),l=a&&t.some(h=>"without_installation"in h),d={current:o,cheapest:n,parts:i,prices:a,without:l};return`
      ${this._flows(e)}
      ${this._span(e)}
      <div class="scroll">
        <table class="plans">
          <thead>${this._head(d)}</thead>
          ${t.map(h=>this._plan(h,d,e)).join("")}
        </table>
      </div>
      ${c.map(zn).join("")}`}_head({parts:e,prices:t,without:s}){let o=[this._labels.plans_plan,...t?[this._labels.plans_prices]:[]],n=(l,d="")=>`<th${hs(d)}>${l}</th>`,a=[n(this._labels.plans_total,"rule"),...s?[n(this._labels.plans_without,"rule")]:[],n(this._labels.plans_vs_current)],i=[n(this._labels.plans_plan),...t?[n(this._labels.plans_prices,"prices")]:[],...e.map((l,d)=>n(this._labels[l.label],this._partClasses(l,d))),...a].join("");if(!e.length)return`<tr>${i}</tr>`;let c=Bn.map(l=>{let d=e.filter(p=>p.group===l.key).length;return`<th class="${l.key==="earn"?"rule earn":"rule"}" colspan="${d}">${this._labels[l.label]}</th>`}).join("");return`<tr class="groups"><th colspan="${o.length}"></th>${c}<th colspan="${a.length}" class="rule"></th></tr>
      <tr>${i}</tr>`}_without(e,t){if(!("without_installation"in e))return'<td class="rule"></td>';let s=us(-e.without_installation,t),o=e.without_installation-e.total,n=u(Math.abs(o),t),a=x(o,t),i=a==="loss"?m(this._labels.plans_costs_more,{amount:n}):m(this._labels.plans_saves,{amount:n}),c=["saves",a].filter(Boolean).join(" ");return`<td class="${["rule",s.tone].filter(Boolean).join(" ")}" data-figure="without:${e.id}">${s.text}<div class="${c}">${i}</div></td>`}_partClasses(e,t){return[t===0||cs[t-1].group!==e.group?"rule":"",e.group==="earn"?"earn":""].filter(Boolean).join(" ")}_prices(e,t){let s=e.rates;if(!s)return"<td></td>";let o=_e(t),n=(d,h)=>`<div>${mt(d)} <span class="rate">${h}</span></div>`,a=s.import_market?[n(this._labels.plans_market_price,"")]:s.prices.map(d=>n(d.name,`${se(d.import,t)} ${o}`)),i=s.export_market?this._labels.plans_market_price:`${se(s.export,t)} ${o}`,c=m(this._labels.plans_per_day,{amount:u(s.daily_charge,t)});return`<td class="prices">${[...a,n(this._labels.plans_export_rate,i),n(this._labels.plans_daily_rate,c)].join("")}</td>`}_flows(e){return this._compared.hours?`<div class="flows">${m(this._labels.plans_flows,{imported:w(this._compared.imported_kwh,e),exported:w(this._compared.exported_kwh,e)})}</div>`:""}_span(e){let t=this._compared.compared_from;if(!t)return"";let s=De(new Date(t),e),o=this._compared.compared_from_plan;return`<div class="flows span">${o?m(this._labels.plans_compared_from_plan,{date:s,plan:mt(o)}):m(this._labels.plans_compared_from_meters,{date:s})}</div>`}_plan(e,{current:t,cheapest:s,parts:o,prices:n,without:a},i){let c=[e.current?["current",this._labels.plans_your_plan]:void 0,e===s?["cheapest",this._labels.plans_cheapest]:void 0].filter(Boolean).map(([W,$e])=>`<span class="tag ${W}">${$e}</span>`).join(""),l=`<th>${mt(e.name)}${Kn(c)}</th>`,d=n?this._prices(e,i):"",h=n?2:1,p=h+o.length+2+(a?1:0);if(J(e)){let W=e.no_price?this._labels.plans_no_price:this._labels.plans_incomplete;return`<tbody data-plan="${e.id}"><tr>${l}${d}
        <td class="incomplete rule" colspan="${p-h}">${W}</td></tr></tbody>`}let v=o.map((W,$e)=>this._part(e,W,i,this._partClasses(W,$e))).join(""),y=t&&e!==t?this._difference(e,t,i):"<td></td>",he=[this._exportNotes(e,i),this._marketNotes(e,i)].join("").trim();return`<tbody data-plan="${e.id}">
      <tr>${l}${d}${v}${this._total(e,i)}${a?this._without(e,i):""}${y}</tr>
      ${he?`<tr class="note"><td colspan="${p}">${he}</td></tr>`:""}
    </tbody>`}_exportNotes(e,t){return[["unpaid",e.export_unpaid,this._labels.plans_export_unpaid],["carried",e.export_carried,this._labels.plans_export_carried]].filter(([,s])=>s>0).map(([s,o,n])=>`<div class="difference" data-figure="export-${s}:${e.id}">${m(n,{amount:u(o,t)})}</div>`).join("")}_marketNotes(e,t){if((e.carried_hours??0)<=0)return"";let s=new Intl.NumberFormat(t.language,{maximumFractionDigits:1}).format(e.carried_hours);return`<div class="difference">${m(this._labels.plans_carried,{hours:s})}</div>`}_resolution(e){let t=this._compared.five_minute_from;if(!t)return this._labels.plans_market_hourly;let s=new Date(t);return s<=this._period.start?this._labels.plans_market_five_minutes:m(this._labels.plans_market_from,{date:De(s,e)})}_total(e,t){return pt(`total:${e.id}`,-e.total,t,"total rule")}_part(e,{key:t,figure:s=t,group:o},n,a=""){let i=o==="earn"?e[s]:-e[s];return pt(`${t}:${e.id}`,i,n,a)}_difference(e,t,s){let o=t.total-e.total;return x(o,s)?pt(`difference:${e.id}`,o,s,"difference"):`<td class="difference" data-figure="difference:${e.id}">${this._labels.plans_same_short}</td>`}},zn=r=>`<div class="hint">${r}</div>`,hs=r=>r?` class="${r}"`:"",us=(r,e)=>{let t=x(r,e),s=t==="loss"?-Math.abs(r):Math.abs(r);return{text:u(s,e),tone:t}},pt=(r,e,t,s="")=>{let{text:o,tone:n}=us(e,t),a=[s,n].filter(Boolean).join(" ");return`<td${hs(a)} data-figure="${r}">${o}</td>`},Kn=r=>r?`<span class="tags">${r}</span>`:"",mt=r=>String(r).replaceAll(/[&<>"']/g,e=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[e]),_t=class extends f{},Yn=()=>{g(ds,_t),_(ls,ft,{name:"Home Energy Advisor: Compare tariff plans",description:"What each tariff plan you have entered would have cost over the selected period, for the whole home."})};Yn();var fs="hea-self-sufficiency-card",_s=`${fs}-editor`,ps=["energyUsed","energyFromGrid","energyFromGeneration","energyFromBattery","energyFromBatterySolar"],qn={maximumFractionDigits:0},ms=.005,gt=class extends F{static titleKey="title_self_sufficiency";static chartTag="ha-gauge";static bearingCard={type:"energy-self-sufficiency-gauge"};static emptyKey="no_energy_in_period";static cardStyle=`
    .intro {
      margin-bottom: var(--hea-space-m);
      color: var(--secondary-text-color);
    }
    .gauges {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
      gap: var(--hea-space-l);
    }
    /* One column, as wide as the cell up to Home Assistant's own cap on an
       energy gauge. A grid rather than a flex column, whose centring would
       shrink the gauge to nothing: its arc sizes itself to the width given. */
    .gauge {
      display: grid;
      grid-template-columns: minmax(0, 250px);
      justify-content: center;
    }
    ha-gauge { display: block; }
    .headline {
      margin-top: var(--hea-space-s);
      text-align: center;
      color: var(--secondary-text-color);
      font-size: 0.85em;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    .share { margin-top: var(--hea-space-l); color: var(--secondary-text-color); }
    .value { color: var(--primary-text-color); font-weight: 500; }
    .note {
      margin-top: var(--hea-space-m);
      color: var(--secondary-text-color);
      font-size: 0.8em;
    }
  `;static getConfigElement(){return document.createElement(_s)}getCardSize(){return 4}_isEmpty(){return this._totals().energyUsed<=0}_totals(){return(this._result?.devices??[]).reduce((e,t)=>{for(let s of ps)e[s]+=t[s];return e},Object.fromEntries(ps.map(e=>[e,0])))}_shares(){let e=this._totals(),t=e.energyUsed,s=c=>e[c]/t,o=s("energyFromBatterySolar"),n=s("energyFromGeneration")+o,a=s("energyFromBattery")-o,i=s("energyFromGrid");return{generation:n,storedSolar:o,battery:a,grid:i,unaccounted:Math.max(0,1-n-a-i)}}_body(e){let t=super._body(e);return!this._chartReady||this._isEmpty()?t:`${t}${this._breakdown(e)}`}_gauges(){let e=this._shares(),t=this._totals().energyFromBattery>0;return[{key:"generation",label:this._labels.from_generation,note:e.storedSolar>ms?this._labels.including_stored_solar:"",colour:"var(--energy-solar-color, #ff9800)"},t&&{key:"storedSolar",label:this._labels.of_which_stored_solar,colour:"var(--energy-solar-color, #ff9800)"},t&&{key:"battery",label:this._labels.from_battery_grid,colour:"var(--energy-battery-out-color, #4db6ac)"},{key:"grid",label:this._labels.from_grid,colour:"var(--energy-grid-consumption-color, #488fc2)"}].filter(Boolean).map(s=>({...s,value:e[s.key]}))}_chartMarkup(){let e=U(this._hass),t=m(this._labels.energy_used_came_from,{energy:w(this._totals().energyUsed,e)}),s=this._gauges().map(({key:o,label:n,note:a,colour:i})=>`
        <div class="gauge">
          <ha-gauge data-gauge="${o}" style="--gauge-color: ${i}"></ha-gauge>
          <div class="headline">${n}</div>
          ${a?`<div class="headline">${a}</div>`:""}
        </div>`).join("");return`<div class="intro" data-figure="energy-used">${t}</div>
      <div class="gauges">${s}</div>`}_breakdown(e){let{unaccounted:t}=this._shares();return`${t>ms?`<div class="share">${this._labels.unaccounted}
            <span class="value" data-share="unaccounted">${q(t,e)}</span></div>`:""}<div class="note">${this._labels.self_sufficiency_note}</div>`}_afterRender(){if(!this._chartReady||this._isEmpty())return;let e=Object.fromEntries(this._gauges().map(({key:t,value:s})=>[t,s]));for(let t of this.shadowRoot.querySelectorAll("ha-gauge"))t.hass=this._hass,t.min=0,t.max=100,t.value=e[t.dataset.gauge]*100,t.label="%",t.formatOptions=qn,t.locale=this._hass?.locale}},yt=class extends f{},Vn=()=>{g(_s,yt),_(fs,gt,{name:"Home Energy Advisor: Self-sufficiency",description:"What share of the selected period's energy came from the household's own generation."})};Vn();var gs="hea-sources-card",ys=`${gs}-editor`,Zn=({energyFromGrid:r,energyUsed:e})=>e>0&&r>=0&&r<=e?r/e:void 0,Xn=[{field:"name",label:"device"},{field:"energyUsed",label:"energy",format:w},{field:"energyFromGrid",label:"grid",format:w},{field:"energyFromGeneration",label:"generation",format:w},{field:"energyFromBattery",label:"battery",format:w},{derive:Zn,label:"from_grid",format:q}],bs={energy_used:{field:"energyUsed",label:"energy_used"},energy_from_grid:{field:"energyFromGrid",label:"from_grid"},energy_from_generation:{field:"energyFromGeneration",label:"from_generation"},energy_from_battery:{field:"energyFromBattery",label:"from_battery"}},bt=class extends P{static titleKey="title_sources";static columns=Xn;static sorts=bs;static defaultSort="energy_used";static getConfigElement(){return document.createElement(ys)}},vt=class extends f{_extraSchema(){return Oe(bs,k(this._hass))}},Qn=()=>{g(ys,vt),_(gs,bt,{name:"Home Energy Advisor: Energy sources",description:"Grid, generation and battery behind each device's energy over the period."})};Qn();var xs="hea-totals-card",ws=`${xs}-editor`,vs=[{key:"actualCost",label:"paid"},{key:"costAtGridPrice",label:"would_have_paid"},{key:"costSavings",label:"saved"}],xt=class extends T{static titleKey="title_totals";static cardStyle=`${be}
    .figures { display: flex; flex-wrap: wrap; gap: var(--hea-space-l); }
    .figure {
      flex: 1 1 8em;
      display: flex;
      flex-direction: column;
      gap: var(--hea-space-xs);
    }
    .compare { color: var(--secondary-text-color); font-size: 0.8em; }
    .label {
      color: var(--secondary-text-color);
      font-size: 0.85em;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    .value {
      color: var(--primary-text-color);
      font-size: 1.6em;
      font-weight: 500;
      white-space: nowrap;
    }
    /*
     * Three figures at 8em plus two gaps need about 368px, and a phone leaves
     * roughly 340px of card - so they wrapped two-then-one, orphaning Saved on
     * a line of its own, and the comparison line wrapped again inside its
     * column (HEA-103). One per row reads better than an uneven grid: the
     * label sits against its figure and nothing is squeezed.
     */
    @media (max-width: 767px) {
      .figures { flex-direction: column; gap: var(--hea-space-m); }
      .figure {
        flex: 1 1 auto;
        flex-direction: row;
        flex-wrap: wrap;
        align-items: baseline;
        justify-content: space-between;
        gap: var(--hea-space-m);
      }
      /* Its own line beneath the pair, rather than a third thing competing
         for the same row - it is a qualification of the figure, not a peer. */
      .compare { flex-basis: 100%; text-align: right; }
    }
  `;static getConfigElement(){return document.createElement(ws)}getCardSize(){return 3}_body(e){let t=this._result?.totals;return`<div class="figures">${(this._result?.gridOnly?vs.slice(0,1):vs).map(({key:n,label:a})=>{let i=t?.[n],c=n==="costSavings"?x(i,e):"",l=c?` ${c}`:"";return`
        <div class="figure">
          <span class="label">${ve(a)}${this._labels[a]}</span>
          <span class="value${l}" data-figure="${n}">${u(i,e)}</span>
          ${this._comparedTo(n,i,e)}
        </div>`}).join("")}</div>`}_comparedTo(e,t,s){let o=this._result?.totals?.before?.[e];if(!Number.isFinite(o)||!Number.isFinite(t))return"";let n=K(e,t-o,s);return`<span class="${n?`compare ${n}`:"compare"}" data-compare="${e}">${m(this._labels.compared,{change:z(t-o,s),before:u(o,s)})}</span>`}},wt=class extends f{},Jn=()=>{g(ws,wt),_(xs,xt,{name:"Home Energy Advisor: Totals",description:"What the selected period cost, what it would have cost at grid price, and the difference."})};Jn();
