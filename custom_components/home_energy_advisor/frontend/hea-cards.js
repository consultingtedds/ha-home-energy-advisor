var ds=[4,4,0,0],us=[0,0,4,4],ut=t=>t!==null&&typeof t=="object"&&!Array.isArray(t),hs=t=>{let e=ut(t)?t.value:t;return Array.isArray(e)?e[1]:e},Se=(t,e)=>{let r=ut(t)?{...t}:{value:t};return{...r,itemStyle:{...r.itemStyle,...e}}},ie=t=>{let e=Math.max(...t.map(({data:s})=>s.length),0),r=t.map(({data:s})=>[...s]);for(let s of ps(t))for(let o=0;o<e;o++)ms(r,o,s);return t.map((s,o)=>({...s,data:r[o]}))},ps=t=>{let e=new Map;return t.forEach((r,s)=>{let o=r.stack??Symbol(s),n=e.get(o);n?n.push(s):e.set(o,[s])}),[...e.values()]},ms=(t,e,r)=>{let s=!1,o=!1;for(let n=r.length-1;n>=0;n--){let a=r[n],i=t[a][e];if(i===void 0)continue;let c=hs(i);c?c>0&&!s?(t[a][e]=Se(i,{borderRadius:ds}),s=!0):c<0&&!o&&(t[a][e]=Se(i,{borderRadius:us}),o=!0):t[a][e]=Se(i,{borderWidth:0})}};var ht="_energy",ke="energy_";var fs=(t,e)=>{let r=t||(e?`${ke}${e}`:"");return r?r.startsWith(ke)?`_${r}`:`_${ke}${r}`:ht},_s=(t,e)=>typeof t=="string"&&t.startsWith(ht)&&e!==null&&typeof e=="object"&&typeof e.subscribe=="function"&&"start"in e,gs=(t=new Date)=>{let e=new Date(t);return e.setDate(e.getDate()-30),e.setHours(0,0,0,0),{start:e,end:t,fallback:!0}},ys=t=>{let e=t?.connection;if(!e)return{};let r={};for(let s of Object.keys(e)){let o;try{o=e[s]}catch{continue}_s(s,o)&&(r[s]=o)}return r},bs=(t,e)=>{let r=ys(t),s=fs(e,t?.panelUrl);if(r[s])return r[s];let[o]=Object.values(r);return o??null},vs=t=>t?.startCompare&&t?.endCompare?{compare:{start:t.startCompare,end:t.endCompare,mode:t.compareMode}}:{},pt=(t,e,r)=>{let s=null,o=null,n=0,a=t,i=l=>{if(s)return!0;let d=bs(l,e);if(!d)return!1;let h=m=>r({start:d.start,end:d.end,fallback:!1,...vs(m)});return s=d.subscribe(h),h(),!0},c=()=>{o=setTimeout(()=>{o=null,n+=1,!i(a)&&n<40&&c()},250)};return r(gs()),i(t)||c(),{retry:l=>(l&&(a=l),i(a)),unsubscribe:()=>{o&&clearTimeout(o),o=null;try{typeof s=="function"&&s()}catch{}s=null}}};var ce="sensor.home_energy_advisor_devices",xs="home_energy_advisor",le=t=>{if(t?.states?.[ce])return ce;let e=t?.entities;if(!e)return ce;for(let[r,s]of Object.entries(e))if(s?.platform===xs&&Array.isArray(t?.states?.[r]?.attributes?.devices))return r;return ce},g=(t,e=void 0)=>{let r=t?.states?.[e??le(t)]?.attributes?.devices;return Array.isArray(r)?r.filter(s=>s?.key).map(_t):[]},L=(t,e=void 0)=>{let r=t?.states?.[e??le(t)]?.attributes?.whole_home;return r?.key?_t(r):null},mt=(t,e=void 0)=>{let r=t?.states?.[e??le(t)]?.attributes?.settled_until;if(typeof r!="string")return null;let s=new Date(r);return Number.isNaN(s.getTime())?null:s},ft=(t,e=void 0)=>{let r=t?.states?.[e??le(t)]?.attributes?.labels;return r&&typeof r=="object"?r:{}},_t=t=>({key:t.key,name:t.name||t.key,deviceId:t.device_id??null,untracked:!!t.untracked,statistics:t.statistics??{},areaId:t.area_id??null,areaName:t.area_name??null,floorId:t.floor_id??null,floorName:t.floor_name??null,upstream:t.upstream??null,gross:!!t.gross,labels:Array.isArray(t.labels)?t.labels:[]});var gt=Object.freeze({kind:"all",id:null}),ws={area:"areaId",floor:"floorId"},Ae=new Map,Oe=t=>(Ae.has(t)||Ae.set(t,{filter:gt,listeners:new Set}),Ae.get(t)),X=t=>Oe(t).filter,de=(t,e)=>{let{listeners:r}=Oe(t);return r.add(e),()=>r.delete(e)},yt=(t,e)=>{let r=Oe(t),s={kind:e?.kind??"all",id:e?.id??null};if(!(s.kind===r.filter.kind&&s.id===r.filter.id)){r.filter=s;for(let o of r.listeners)try{o(s)}catch(n){console.warn("home-energy-advisor: a card could not follow the filter",n)}}},bt=(t,e)=>{let{kind:r,id:s}=e??gt;if(r==="all")return!0;if(r==="device")return t.key===s;if(t.untracked)return!1;if(r==="label")return(t.labels??[]).includes(s);let o=ws[r];return o?(t[o]??null)===s:!0};var Es={day:"numeric",month:"short",year:"numeric"},ue=t=>({language:t?.locale?.language||void 0,currency:t?.config?.currency||void 0,timeFormat:t?.locale?.time_format||void 0,timeZone:t?.locale?.time_zone==="server"?t?.config?.time_zone:void 0}),Ss=({timeFormat:t,language:e})=>{if(t==="language"||t==="system"||!t){let r=t==="system"?void 0:e;return new Date("January 1, 2023 22:00:00").toLocaleString(r).includes("10")}return t==="12"},vt=(t,e)=>new Intl.DateTimeFormat(e.language,{hour:"numeric",minute:"2-digit",hourCycle:Ss(e)?"h12":"h23",timeZone:e.timeZone}).format(t),ks=(t,e)=>new Intl.DateTimeFormat(e.language,{weekday:"short",month:"short",day:"numeric",timeZone:e.timeZone}).format(t),As={hour:3600*1e3},xt=(t,e,r)=>{let s=As[e];if(!s)return ks(t,r);let o=new Date(t.getTime()+s);return`${vt(t,r)} \u2013 ${vt(o,r)}`},u=(t,{language:e,currency:r})=>typeof t!="number"||!Number.isFinite(t)?"-":new Intl.NumberFormat(e,{...wt(r),signDisplay:"negative"}).format(t),wt=t=>t?{style:"currency",currency:t}:{minimumFractionDigits:2,maximumFractionDigits:2},Et=(t,{language:e,currency:r}={})=>{let o=10**new Intl.NumberFormat(e,wt(r)).resolvedOptions().maximumFractionDigits;return Math.round(t*o)/o},U=(t,{language:e,currency:r})=>{if(typeof t!="number"||!Number.isFinite(t))return"-";let s=r?{style:"currency",currency:r,signDisplay:"exceptZero"}:{minimumFractionDigits:2,maximumFractionDigits:2,signDisplay:"exceptZero"};return new Intl.NumberFormat(e,s).format(t)},Os=new Set(["actualCost","costAtGridPrice","energyUsed"]),Ts=new Set(["costSavings"]),k=(t,e)=>{if(typeof t!="number"||!Number.isFinite(t))return"";let r=Et(t,e);return r===0?"":r>0?"gain":"loss"},Cs=new Set(["actualCost","costAtGridPrice","costSavings"]),W=(t,e,r)=>{if(typeof e!="number"||!Number.isFinite(e))return"";let s=Cs.has(t)?Et(e,r):e;return s===0?"":Os.has(t)?s<0?"gain":"loss":Ts.has(t)?s>0?"gain":"loss":""},z=(t,e)=>{if(!Array.isArray(t))return"-";let[r,s]=t;if(![r,s].every(a=>Number.isFinite(a)))return"-";if(r===s)return u(r,e);let[o,n]=r<=s?[r,s]:[s,r];return`${u(o,e)} - ${u(n,e)}`},R=(t,{language:e})=>typeof t!="number"||!Number.isFinite(t)?"-":`${new Intl.NumberFormat(e,{maximumFractionDigits:1}).format(t)} kWh`,St={EUR:{symbol:"c",per:100},USD:{symbol:"\xA2",per:100},GBP:{symbol:"p",per:100}},Q=(t,{language:e})=>typeof t!="number"||!Number.isFinite(t)?"-":new Intl.NumberFormat(e,{minimumFractionDigits:t===0?0:2,maximumFractionDigits:2}).format(t),J=({language:t,currency:e})=>e?kt(t,e):"",kt=(t,e)=>new Intl.NumberFormat(t,{style:"currency",currency:e}).formatToParts(0).find(r=>r.type==="currency")?.value??"",At=({language:t,currency:e})=>{if(!e)return"/kWh";let r=St[e];return`${r?r.symbol:kt(t,e)}/kWh`},Ot=(t,{language:e,currency:r})=>{if(typeof t!="number"||!Number.isFinite(t))return"-";let s=r?St[r]:void 0;return new Intl.NumberFormat(e,{minimumFractionDigits:s?1:0,maximumFractionDigits:s?2:3}).format(s?t*s.per:t)},K=(t,{language:e})=>typeof t!="number"||!Number.isFinite(t)?"-":new Intl.NumberFormat(e,{style:"percent",maximumFractionDigits:0}).format(t),b=t=>String(t).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#39;"),ee=(t,{language:e})=>t?new Intl.DateTimeFormat(e,Es).formatRange(t.start,t.end):"";var Ct="common",$t="home_energy_advisor",Tt=`component.${$t}.${Ct}.card_`,Ce=Object.freeze({paid:"Paid",would_have_paid:"Would have paid",saved:"Saved",lost:"Lost",range_column:"Paid (min-max)",range_note:"Paid (min-max) is the widest range these readings allow, not a typical error: a meter that reports every 30-90 minutes leaves the exact moment of use unknown.",range_whole_home:"What you paid could honestly sit between {range} - the widest these readings allow, not a typical error.",range_device:"What you paid could be between {range}.",range_note_rollover:"Hover over or tap a figure in Paid to see the range it could honestly have been. That range is the widest these readings allow, not a typical error: a meter that reports every 30-90 minutes leaves the exact moment of use unknown.",forgone_column:"Could have earned",forgone_note:"Could have earned is what the generation each device used could have earned had you exported it instead, at your export rate at the time. It is money you did not receive, not money you paid, and it is not part of Paid.",forgone_hidden_note:"Could have earned, what the generation each device used could have earned had you exported it instead, is shown on a wider screen.",compared:"{change} vs {before}",compared_period:"{period} vs {compared}",saved_share:"{percent} of what you would have paid was saved.",lost_share:"{percent} more was paid than the grid would have cost.",change:"Change",compared_series:"Earlier period",device:"Device",energy:"Energy",rate:"Rate",total:"Total",grid:"Grid",generation:"Generation",battery:"Battery",from_grid:"From the grid",from_generation:"From generation",from_battery:"From the battery",from_battery_grid:"From battery (grid)",including_stored_solar:"including stored solar",energy_used:"Energy used",unaccounted:"Unaccounted",self_sufficiency_note:"Solar stored in the battery counts as your own. Battery energy charged from the grid does not, and is shown on its own.",household:"Household",generation_saved:"Generation saved",battery_saved:"Battery saved",exports_earned:"Exports earned",installation_note:"For the whole home: your own generation, your battery and your exports, measured against your current tariff. What the battery lost is taken off what it saved.",no_installation:"There is no generation or battery here, so nothing for an installation to have earned.",title_installation:"What your installation earned",title_plans:"Compare tariff plans",tab_summary:"Summary",tab_devices:"Devices",tab_tariffs:"Tariffs",plans_your_plan:"Your plan",plans_cheapest:"Cheapest",plans_energy:"Energy",plans_export:"Export",plans_daily:"Daily charges",plans_less:"{amount} less than your plan",plans_more:"{amount} more than your plan",plans_same:"The same as your plan",plans_incomplete:"Not every hour has a price, so it cannot be compared. Edit the plan to finish its bands.",plans_note:"For the whole home: each plan priced at the electricity you actually imported and exported, as if your battery had run the same way. Prices are compared as you entered them.",plans_no_readings:"Your grid meters recorded nothing in this period, so only the daily charges are shown.",plans_no_current:"Mark one plan as the one you are on to see how the others compare.",no_plans:"No tariff plans yet. Add one from the Home Energy Advisor integration, with Add tariff plan.",title_totals:"Cost summary",title_devices:"Cost by device",title_device_costs:"What each device cost",title_cost_over_time:"Cost over time",title_sources:"Where the energy came from",title_self_sufficiency:"Self-sufficiency",title_distribution:"Where the cost went",title_distribution_energy:"Where the energy went",no_devices:"No devices are being tracked yet.",no_devices_in_filter:"No tracked device matches what the page is showing.",title_filter:"Show",filter_everything:"Everything",filter_rooms:"Rooms",filter_floors:"Floors",filter_labels:"Labels",filter_devices:"Devices",filter_unfiled:"Not in one",device_untracked:"Untracked",hourly_shape_estimate:"One device's hourly shape is an estimate: each meter reading is spread across the hours it spanned, so cost may not land in the hour the energy was used.",still_accruing:"The last interval is still being counted, so its bar will grow. Figures are complete about twenty minutes behind the clock, which is how long meters are given to report.",statistics_failed:"Statistics could not be loaded.",no_picker:"Add an Energy date picker card to choose the range.",chart_not_loaded:"Home Assistant's chart component is not loaded. Adding any energy or statistics card to this dashboard will load it.",no_cost_in_period:"No cost recorded in this period.",no_energy_in_period:"No energy recorded in this period.",editor_title:"Title",editor_collection_key:"Energy period (collection key)",editor_devices:"Devices (all, if none are chosen)",editor_sort_by:"Order by",editor_layout:"Layout",editor_metric:"Measure by",editor_group_by_floor:"Group by floor",editor_group_by_area:"Group by area",editor_range:"Show the cost range as",editor_range_auto:"Automatic: a column where there is room",editor_range_rollover:"A rollover on Paid",editor_range_column:"Its own column"}),Te=new Map,Ft=new Map,Rt=t=>t?.locale?.language||t?.language||"en",A=t=>{let e=Rt(t);return Te.has(e)||Te.set(e,$s(t,e).then(r=>(Ft.set(e,r),r))),Te.get(e)},$s=async(t,e)=>{try{let{resources:r}=await t.callWS({type:"frontend/get_translations",language:e,category:Ct,integration:[$t]});return Object.freeze({...Ce,...Fs(r)})}catch(r){return console.warn("home-energy-advisor: falling back to English labels",r),Ce}},x=t=>Ft.get(Rt(t))??Ce,Fs=t=>Object.fromEntries(Object.entries(t??{}).filter(([e,r])=>e.startsWith(Tt)&&r).map(([e,r])=>[e.slice(Tt.length),r])),v=(t,e)=>Object.entries(e).reduce((r,[s,o])=>r.replaceAll(`{${s}}`,o),t);var w=Object.freeze({energyUsed:"energy_used",actualCost:"actual_cost",costAtGridPrice:"cost_at_grid_price",energyFromGrid:"energy_from_grid",energyFromGeneration:"energy_from_generation",energyFromBattery:"energy_from_battery",energyFromBatterySolar:"energy_from_battery_solar",forgoneExport:"forgone_export"}),N=Object.freeze({costFloor:"lowest_possible_cost",costCeiling:"highest_possible_cost"}),$e=()=>Object.fromEntries(Object.keys(w).map(t=>[t,0])),Dt=1440*60*1e3,Lt={hour:3600*1e3,day:Dt},Rs=2,Y=(t,e)=>t?.statistics?.[e],te=t=>w.costAtGridPrice in(t?.statistics??{}),Mt=(t,e,r,s=!1)=>e==="costAtGridPrice"&&!te(t)?Y(t,w.actualCost):e==="energyFromGrid"&&s?Y(t,w.energyUsed):Y(t,r),Is=t=>[w.energyFromGrid,w.energyFromGeneration,w.energyFromBattery].some(e=>e in(t?.statistics??{})),Ns=t=>t.length>0&&!t.some(Is),he=(t,e=[])=>{let r=g(t);return Ns(r.length?r:e)},Ds=(t,e)=>{let r=t.flatMap(s=>[...Object.values(w),...Object.values(N)].map(o=>Y(s,o)).filter(Boolean));return!e?.statistics||t.length===0?r:[...r,...Object.values(N).map(s=>Y(e,s)).filter(Boolean)]},Gt=(t,e)=>{if(!e)return t;let r=new Map(e.devices.map(s=>[s.key,s]));return{...t,totals:{...t.totals,before:e.totals},devices:t.devices.map(s=>({...s,before:r.get(s.key)})),seriesBefore:Ls(e.series,t.period,e.period)}},Ls=(t,e,r)=>{if(!t?.length)return;let s=e.start.getTime()-r.start.getTime();return t.map(o=>({...o,start:new Date(o.start.getTime()+s),actualStart:o.start}))},C=({start:t,end:e})=>e-t>Rs*Dt?"day":"hour",It=(t,e,r)=>{if(e!=="day")return new Date(t.getTime()+r*Lt.hour);let s=new Date(t);return s.setDate(s.getDate()+r),s},Pt=(t,e)=>{if(!t.length||!e)return t;let r=C(e),s=new Map(t.map(a=>[a.start.getTime(),a])),o=t[0].start,n=[];for(let a=0;;a--){let i=It(o,r,a);if(i.getTime()<e.start.getTime())break;n.push(s.get(i.getTime())??Nt(i))}n.reverse();for(let a=1;;a++){let i=It(o,r,a);if(i.getTime()>=e.end.getTime())break;n.push(s.get(i.getTime())??Nt(i))}return n},Nt=t=>({...$e(),start:t,costSavings:0,accruing:!1}),Fe=async(t,e,r,s,o=null)=>{let n=Ds(e,s),a=n.length?await t.callWS({type:"recorder/statistics_during_period",start_time:r.start.toISOString(),end_time:r.end.toISOString(),statistic_ids:n,period:C(r),types:["change"]}):{},i=he(t,e),c=Ps(e.map(l=>Gs(l,a,r,i)));return{period:r,gridOnly:i,devices:c,totals:js(c),wholeHome:Ht(s,a,r),series:Ms(e,a,r,o,i)}},Ht=(t,e,r)=>{if(!t)return;let s={};for(let[o,n]of Object.entries(N)){let a=e?.[Y(t,n)];if(!Array.isArray(a))return;s[o]=Bt(a,r)}return s},Ms=(t,e,r,s,o)=>{let n=new Map,a=new Set(t.filter(c=>c.gross).map(c=>c.key));for(let c of t.filter(l=>!a.has(l.upstream)))for(let[l,d]of Object.entries(w)){let h=e?.[Mt(c,l,d,o)];for(let m of jt(h,r)){let S=n.get(m.start)??$e();S[l]+=m.change,n.set(m.start,S)}}let i=Lt[C(r)]??0;return[...n.entries()].sort(([c],[l])=>c-l).map(([c,l])=>({...l,start:new Date(c),costSavings:l.costAtGridPrice-l.actualCost,accruing:s?c+i>s.getTime():!1}))},Gs=(t,e,r,s)=>{let o=Object.fromEntries(Object.entries(w).map(([n,a])=>[n,Bt(e?.[Mt(t,n,a,s)],r)]));return{...t,...o,...Ht(t,e,r),costSavings:o.costAtGridPrice-o.actualCost}},Ps=t=>{let e=new Map;for(let r of t)r.upstream&&e.set(r.upstream,[...e.get(r.upstream)??[],r]);return t.map(r=>{if(!r.gross)return r;let s={...r};for(let o of Object.keys(w)){let n=(e.get(r.key)??[]).reduce((a,i)=>a-i[o],r[o]);s[o]=Math.abs(n)<Hs(o)?0:n}return s.costSavings=s.costAtGridPrice-s.actualCost,s})},Hs=t=>t.startsWith("energy")?5e-4:.005,jt=(t,{start:e,end:r})=>{if(!Array.isArray(t))return[];let s=[];for(let o of t){let n=new Date(o.start).getTime();n<e.getTime()||n>=r.getTime()||typeof o.change=="number"&&s.push({start:n,change:o.change})}return s},Bt=(t,e)=>jt(t,e).reduce((r,s)=>r+s.change,0),js=t=>({...t.reduce((r,s)=>{for(let o of Object.keys(r))r[o]+=s[o];return r},{...$e(),costSavings:0}),...Bs(t)}),Bs=t=>{let e=Object.keys(N);return!t.length||!t.every(r=>e.every(s=>s in r))?{}:Object.fromEntries(e.map(r=>[r,t.reduce((s,o)=>s+o[r],0)]))};var Us=`
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
`,Ws=`
  .loss { color: var(--error-color, #db4437); }
  .gain { color: var(--success-color, #4caf50); }
`,M="(max-width: 767px)",O=class extends HTMLElement{static cardStyle="";static narrowQuery="";static titleKey="";_titleKey(){return this.constructor.titleKey}get _labels(){return x(this._hass)}constructor(){super(),this.attachShadow({mode:"open"}),this._state="loading",this._request=0}setConfig(e){if(e.devices!==void 0&&!Array.isArray(e.devices))throw new Error("`devices` must be a list of device keys");this._config=e,this._render()}set hass(e){this._hass=e,this._subscription?this._subscription.retry(e):this._subscribe(),this._refetchIfDevicesChanged()}connectedCallback(){this._render(),this._hass&&!this._subscription&&this._subscribe(),this._watchScreen()}disconnectedCallback(){this._subscription?.unsubscribe(),this._subscription=null,this._unfilter?.(),this._unfilter=null,this._screen?.removeEventListener?.("change",this._onScreenChange),this._screen=null}_watchScreen(){let{narrowQuery:e}=this.constructor;!e||this._screen||(this._screen=globalThis.matchMedia?.(e),this._onScreenChange??=()=>this._render(),this._screen?.addEventListener?.("change",this._onScreenChange))}_isNarrow(){return!!globalThis.matchMedia?.(M)?.matches}_subscribe(){this._subscription=pt(this._hass,this._config?.collection_key,e=>{this._period=e,this._scheduleFetch()}),this._unfilter=de(this._config?.collection_key,()=>this._scheduleFetch())}_scheduleFetch(){this._fetchPending||(this._fetchPending=!0,queueMicrotask(()=>{this._fetchPending=!1,this._fetch()}))}_refetchIfDevicesChanged(){let e=this._devices().map(r=>r.key).join(",");e!==this._deviceKeys&&(this._deviceKeys=e,this._period&&this._scheduleFetch())}_devices(){let e=g(this._hass),r=this._config?.devices,s=r?e.filter(n=>r.includes(n.key)):e,o=this._filter();return s.filter(n=>bt(n,o))}_filter(){return X(this._config?.collection_key)}_isFiltered(){return!!this._config?.devices||this._filter().kind!=="all"}async _fetch(){if(!this._hass||!this._period)return;let e=this._devices(),r=++this._request;if(await A(this._hass),e.length===0){this._state="empty",this._render();return}let s=this._isFiltered()?void 0:L(this._hass);try{let o=mt(this._hass),[n,a]=await Promise.all([Fe(this._hass,e,this._period,s,o),this._period.compare?Fe(this._hass,e,this._period.compare,s):void 0]);if(r!==this._request)return;this._result=Gt(n,a),this._state="ready"}catch(o){if(r!==this._request)return;this._state="error",console.error(`${this.localName}: could not load statistics`,o)}this._render()}_render(){let e=ue(this._hass);this.shadowRoot.innerHTML=`
      <style>${Us}${this.constructor.cardStyle}${Ws}</style>
      <ha-card>
        <div class="body" data-state="${this._state}">${this._content(e)}</div>
      </ha-card>
    `;let r=this._config?.title??this._labels[this._titleKey()];r&&this._writeHeader(r,e),this._afterRender()}_writeHeader(e,r){let s=this.shadowRoot.querySelector("ha-card"),o=this._headerChip(r);if(o===void 0){s.setAttribute("header",e);return}s.insertAdjacentHTML("afterbegin",`<div class="card-header" style="display: flex; justify-content: space-between;
         align-items: center; gap: var(--hea-space-s); padding-bottom: 0;">
        <span class="title">${b(e)}</span>
        <span class="chip">${b(o)}</span>
      </div>`)}_headerChip(){}_afterRender(){}_content(e){return this._state==="empty"?`<p class="message">${this._labels.no_devices}</p>`:this._state==="error"?`<p class="message">${this._labels.statistics_failed}</p>`:`${this._body(e)}${this._caption(e)}`}_caption(e){let r=this._period?.fallback?`<div class="hint">${this._labels.no_picker}</div>`:"";return`<div class="period">${this._periodLabel(e)}</div>${r}`}_periodLabel(e){let r=ee(this._period,e),s=this._period?.compare;return s?v(this._labels.compared_period,{period:r,compared:ee(s,e)}):r}},f=(t,e,{name:r,description:s})=>{customElements.get(t)||customElements.define(t,e),globalThis.customCards=globalThis.customCards??[],globalThis.customCards.some(o=>o.type===t)||globalThis.customCards.push({type:t,name:r,description:s})};var zs={title:"editor_title",collection_key:"editor_collection_key",devices:"editor_devices",sort_by:"editor_sort_by",layout:"editor_layout",metric:"editor_metric",group_by_floor:"editor_group_by_floor",group_by_area:"editor_group_by_area",range:"editor_range"},p=class extends HTMLElement{constructor(){super(),this.attachShadow({mode:"open"})}setConfig(e){this._config=e,this._render()}set hass(e){this._hass=e,this._render(),A(e).then(()=>this._render())}_extraSchema(){return[]}_render(){if(!this._config)return;let e=this.shadowRoot.querySelector("ha-form");e||(e=document.createElement("ha-form"),e.computeLabel=r=>x(this._hass)[zs[r.name]]??r.name,e.addEventListener("value-changed",r=>this._report(r.detail.value)),this.shadowRoot.append(e)),e.hass=this._hass,e.data=this._config,e.schema=this._schema()}_schema(){return[{name:"title",selector:{text:{}}},{name:"collection_key",selector:{text:{}}},{name:"devices",selector:{select:{multiple:!0,mode:"list",options:g(this._hass).map(e=>({value:e.key,label:e.name}))}}},...this._extraSchema()]}_report(e){this.dispatchEvent(new CustomEvent("config-changed",{detail:{config:Ks({...this._config,...e})},bubbles:!0,composed:!0}))}},Ks=t=>Object.fromEntries(Object.entries(t).filter(([,e])=>e!==""&&e!==void 0&&e!==null&&!(Array.isArray(e)&&e.length===0))),_=(t,e)=>{customElements.get(t)||customElements.define(t,e)};var $=class extends O{static chartTag="ha-chart-base";static bearingCard={type:"statistics-graph",entities:[]};static emptyKey="no_cost_in_period";static chartHeight="clamp(320px, 40vw, 480px)";static cardStyle=`
    ha-chart-base { display: block; --chart-max-height: none; }
  `;constructor(){super(),this._chartReady=!!customElements.get(this.constructor.chartTag)}getCardSize(){return 6}connectedCallback(){super.connectedCallback(),this._chartReady||this._loadChartComponent()}async _loadChartComponent(){let{chartTag:e,bearingCard:r}=this.constructor;customElements.whenDefined(e).then(()=>{this._chartReady=!0,this._render()});try{await(await globalThis.loadCardHelpers?.())?.createCardElement(r)}catch(s){console.warn(`${e}: could not be loaded`,s)}}_isEmpty(){return(this._result?.series??[]).length===0}_body(){return this._chartReady?this._isEmpty()?`<p class="message">${this._labels[this._emptyKey()]}</p>`:this._chartMarkup():`<p class="message">${this._labels.chart_not_loaded}</p>`}_emptyKey(){return this.constructor.emptyKey}_chartMarkup(){return'<ha-chart-base chart-type="bar"></ha-chart-base>'}_afterRender(){let e=this.shadowRoot.querySelector(this.constructor.chartTag);e&&(e.hass=this._hass,this._draw(e))}_chartHeight(){return this.constructor.chartHeight}_draw(e){e.height=this._chartHeight(),e.data=this._series(),e.options=this._options(this._chartLocale())}_chartLocale(){return ue(this._hass)}_colour({variable:e,fallback:r}){return getComputedStyle(this).getPropertyValue(e).trim()||r}};var Ys=/^#([\da-f]{3}|[\da-f]{6})$/i,qs=/^rgba?\(([^)]+)\)$/i,Re=t=>{let e=Ys.exec(String(t).trim());if(e){let o=e[1];return(o.length===3?[...o].map(a=>a+a):[0,2,4].map(a=>o.slice(a,a+2))).map(a=>Number.parseInt(a,16))}let r=qs.exec(String(t).trim());if(!r)return;let s=r[1].split(/[\s,/]+/).filter(Boolean).slice(0,3).map(Number);return s.length===3&&s.every(Number.isFinite)?s:void 0},I=(t,e)=>{let r=Re(String(t).trim());return r?`rgba(${r.join(", ")}, ${e})`:t},Vs=([t,e,r])=>(.2126*t+.7152*e+.0722*r)/255,pe=t=>{let e=Re(Zs(t));return e?Vs(e)>.5:!1},Zs=t=>{let e=[t,t?.ownerDocument?.documentElement].filter(Boolean);for(let r of e){let s=getComputedStyle(r),o=s.getPropertyValue("--primary-text-color").trim()||s.color;if(Re(o))return o}return""};var Ut=Object.freeze({variable:"--primary-color",fallback:"#03a9f4"}),Wt=Object.freeze({variable:"--success-color",fallback:"#4caf50"}),Xs=Object.freeze({paid:"paid",would_have_paid:"would-have-paid",saved:"saved"}),me=`
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
`,fe=t=>{let e=typeof t=="string"?Xs[t]:void 0;return e?`<span class="swatch ${e}" aria-hidden="true"></span>`:""};var D=(t,e,r,{bold:s=!1}={})=>{let o=document.createElement("div");o.style.display="flex",o.style.justifyContent="space-between",o.style.gap="16px",s&&(o.style.fontWeight="bold");let n=document.createElement("span");n.textContent=t;let a=document.createElement("span");return a.textContent=e,a.style.fontVariantNumeric="tabular-nums",r&&(a.style.color=r),o.append(n,a),o},Qs=t=>{let e=document.createElement("span");return e.style.display="inline-block",e.style.width="10px",e.style.height="10px",e.style.borderRadius="10px",e.style.marginInlineEnd="4px",e.style.verticalAlign="middle",e.style.backgroundColor=t,e},zt=(t,e,r,s)=>{let o=D(e,r,s);return o.firstChild.prepend(Qs(t)),o},_e=t=>{let e=document.createElement("div");return e.textContent=t,e.style.fontWeight="bold",e.style.textAlign="center",e.style.marginBottom="4px",e},Kt=t=>{let e=document.createElement("div");return e.textContent=t,e.style.marginTop="4px",e.style.maxWidth="260px",e.style.whiteSpace="normal",e.style.opacity="0.7",e};var Zt="hea-cost-over-time-card",Xt=`${Zt}-editor`,Js={hour:3600*1e3,day:1440*60*1e3},eo=50,to=.5,ro=(t,e)=>{if(!t.length||!e)return 0;let r=Js[C(e)]??0,s=t.length>=2?t[1].start.getTime()-t[0].start.getTime():void 0;return(s?Math.min(s,r):r)/2},G={paid:{id:"paid",name:"paid",...Ut},saved:{id:"saved",name:"saved",...Wt}},Qt={variable:"--error-color",fallback:"#db4437"},so={gain:{variable:"--success-color",fallback:"#4caf50"},loss:Qt},Ie=t=>t.value?.[1]??0,oo=t=>t.value?.[2],no=.45,ge={id:"before",name:"compared_series",variable:"--secondary-text-color",fallback:"#727272"},Ne=class extends ${static titleKey="title_cost_over_time";static getConfigElement(){return document.createElement(Xt)}_series(){let e=Pt(this._result?.series??[],this._result?.period),r=this._colour(Qt),s=this._labels,o=this._result?.seriesBefore,n=ro(e,this._result?.period),a={...Vt(G.paid,this._colour(G.paid),s),data:e.map(c=>Yt(c,qt(c,c.actualCost,n)))},i={...Vt(G.saved,this._colour(G.saved),s),data:e.map(c=>{let l=qt(c,c.costSavings,n),d=c.costSavings<0?Jt(r):void 0;return Yt(c,l,d)})};return[...ie(this._result?.gridOnly?[a]:[a,i]),...o?.length?[{id:ge.id,name:s[ge.name],type:"line",symbol:"none",lineStyle:{type:"dashed",width:2},itemStyle:{color:this._colour(ge)},data:o.map(c=>[c.start.getTime()+n,c.costAtGridPrice])}]:[]]}_caption(e){return`${super._caption(e)}${this._stillAccruingNote()}`+this._accrualNote()}_stillAccruingNote(){return(this._result?.series??[]).some(e=>e.accruing)?`<div class="hint">${this._labels.still_accruing}</div>`:""}_accrualNote(){return this._devices().length!==1||!this._period||C(this._period)!=="hour"?"":`<div class="hint">${this._labels.hourly_shape_estimate}</div>`}_tooltipFor(e,r){let s=(Array.isArray(e)?e:[e]).filter(c=>c.componentSubType==="bar"),o=s.filter(c=>Ie(c)!==0);if(!o.length)return;let n=this._bucketAt(s.map(oo).find(c=>c!==void 0)),a=document.createElement("div");a.append(_e(this._spanOf(n,r)));for(let c of o)a.append(this._tooltipRowFor(c,r));let i=s.reduce((c,l)=>c+Ie(l),0);return o.length>1&&a.append(D(this._labels.would_have_paid,u(i,r),void 0,{bold:!0})),n?.accruing&&a.append(Kt(this._labels.still_accruing)),a}_tooltipRowFor(e,r){let s=Ie(e),o=e.seriesId===G.saved.id?k(s,r):"",n=o==="loss"?this._labels.lost:e.seriesName;return zt(e.color,n,u(s,r),o?this._colour(so[o]):void 0)}_bucketAt(e){if(e!==void 0)return(this._result?.series??[]).find(r=>r.start.getTime()===e)}_spanOf(e,r){return!e||!this._period?"":xt(e.start,C(this._period),r)}_headerChip(e){let r=this._result?.totals?.actualCost;return Number.isFinite(r)&&!this._isEmpty()?u(r,e):""}_axisBounds(){if(!this._period)return{};let{start:e,end:r}=this._period,s=new Date(r.getTime()-1);return C(this._period)==="hour"?s.setMinutes(30,0,0):(s.getHours()===0&&s.setHours(s.getHours()-1),s.setHours(0,0,0,0)),{min:e.getTime(),max:s.getTime()}}_options(e){let r=this._labels;return{xAxis:{type:"time",...this._axisBounds()},grid:{top:15,bottom:0,left:1,right:1,containLabel:!0},yAxis:{type:"value",name:J(e),nameGap:2,nameTextStyle:{align:"left"},boundaryGap:[0,0],splitNumber:5,splitLine:{show:!0},axisLabel:{formatter:s=>Q(s,e),hideOverlap:!0}},tooltip:{trigger:"axis",axisPointer:{type:"shadow"},formatter:s=>this._tooltipFor(s,e)},legend:{show:!0,type:"custom",data:[G.paid,G.saved,...this._result?.seriesBefore?.length?[ge]:[]].map(s=>({id:s.id,name:r[s.name],itemStyle:{color:this._colour(s)}}))}}}},Yt=(t,e,r=void 0)=>t.accruing?{value:e,itemStyle:{...r,opacity:no}}:r?{value:e,itemStyle:r}:e,qt=(t,e,r)=>[t.start.getTime()+r,e,t.start.getTime()],Vt=({id:t,name:e},r,s)=>({id:t,name:s[e],type:"bar",stack:"cost",barMaxWidth:eo,itemStyle:Jt(r)}),Jt=t=>({color:I(t,to),borderColor:t,borderWidth:1}),De=class extends p{},ao=()=>{_(Xt,De),f(Zt,Ne,{name:"Home Energy Advisor: Cost over time",description:"What the period cost, stacked against what it would have cost at grid price."})};ao();var re=(t,e)=>{let r=e?.statistics?.cost_savings;return!!(r&&t?.states?.[r])},er=(t,e)=>({costSavings:t?.statistics?.cost_savings,batterySavings:t?.statistics?.battery_savings,lossesPaid:(e??[]).filter(r=>!r.untracked&&!r.upstream).filter(r=>!te(r)).map(r=>r.statistics?.actual_cost).filter(Boolean)}),tr=(t,e)=>{let r=e?.cost_sensors??{},s=[];for(let o of t?.energy_sources??[]){if(o?.type!=="grid")continue;let n=Array.isArray(o.flow_to)?o.flow_to:[o];for(let a of n){let i=a?.stat_compensation||a?.stat_energy_to&&r[a.stat_energy_to];i&&!s.includes(i)&&s.push(i)}}return s},rr=t=>[t.costSavings,t.batterySavings,...t.lossesPaid??[],...t.exportsEarned??[]].filter(Boolean),sr=(t,e,r)=>{let s=m=>io(t?.[m],r),o=s(e.costSavings),n=!!e.batterySavings,a=n?s(e.batterySavings):0,i=(e.lossesPaid??[]).reduce((m,S)=>m+s(S),0),c=e.exportsEarned??[],l=o-a,d=n?a-i:void 0,h=c.length?c.reduce((m,S)=>m+s(S),0):void 0;return{generationSaved:l,batterySaved:d,exportsEarned:h,total:l+(d??0)+(h??0)}},io=(t,{start:e,end:r})=>{if(!Array.isArray(t))return 0;let s=0;for(let o of t){let n=new Date(o.start).getTime();n<e.getTime()||n>=r.getTime()||typeof o.change=="number"&&(s+=o.change)}return s};var He="hea",ar="Home Energy Advisor",co="mdi:home-lightning-bolt",or=`ll-strategy-dashboard-${He}`,nr=`ll-strategy-view-${He}`,E=4,ir=[{type:"custom:hea-totals-card"},{type:"custom:hea-devices-card",sort_by:"actual_cost"}],cr=[{type:"custom:hea-cost-over-time-card"},{type:"custom:hea-sources-card",sort_by:"energy_used"}],Me=[{type:"custom:hea-device-costs-card"},{type:"custom:hea-distribution-card"},{type:"custom:hea-self-sufficiency-card"}],lr={type:"custom:hea-installation-card"},lo=new Set(["custom:hea-sources-card","custom:hea-self-sufficiency-card"]),ye=(t,e)=>e?t.filter(r=>!lo.has(r.type)):t,uo=t=>re(t,L(t))?[...Me,lr]:Me,ho=t=>({...t,grid_options:{columns:"full",rows:"auto"}}),T=(t,e)=>({type:"grid",column_span:e,cards:t.map(ho)}),po=()=>({card:{type:"horizontal-stack",cards:[{type:"energy-date-selection",vertical_opening_direction:"up"},{type:"custom:hea-filter-card"}]},max_width:1600}),dr=t=>({type:"sections",max_columns:E,sections:[{type:"grid",cards:[{type:"markdown",content:x(t).no_devices}]}]}),ur={type:"custom:hea-plans-card"},mo=async t=>{try{let e=await t.callWS({type:"home_energy_advisor/list_plans"});return Array.isArray(e?.plans)&&e.plans.length>0}catch{return!1}},hr=t=>({type:"sections",max_columns:E,sections:t.filter(e=>e.cards.length>0),footer:po()}),fo=(t,e)=>{if(g(t).length===0)return dr(t);let r=he(t);return hr([T(ir,E),T(ye(cr,r),E/2),T(ye(uo(t),r),E/2),...e?[T([ur],E)]:[]])},[_o,go]=ir,[yo,bo]=cr,[vo,xo,wo]=Me,Le=(t,{path:e,titleKey:r,icon:s},o)=>({...hr(o),path:e,title:x(t)[r],icon:s}),Eo=(t,e)=>{if(g(t).length===0)return[dr(t)];let r=he(t),s=re(t,L(t))?[lr]:[],o=[Le(t,{path:"summary",titleKey:"tab_summary",icon:"mdi:view-dashboard"},[T([_o],E),T([yo,...s],E/2),T(ye([xo,wo],r),E/2)]),Le(t,{path:"devices",titleKey:"tab_devices",icon:"mdi:format-list-bulleted"},[T([go],E),T([vo],E/2),T(ye([bo],r),E/2)])];return e&&o.push(Le(t,{path:"tariffs",titleKey:"tab_tariffs",icon:"mdi:cash-multiple"},[T([ur],E)])),o},pr=async t=>{let[,e]=await Promise.all([A(t),mo(t)]);return e},Ge=class extends HTMLElement{static async generate(e,r){return{views:Eo(r,await pr(r))}}static noEditor=!0;static getCreateSuggestions(){return{title:ar,icon:co}}},Pe=class extends HTMLElement{static async generate(e,r){return fo(r,await pr(r))}},So=t=>{globalThis.customStrategies=globalThis.customStrategies??[],globalThis.customStrategies.some(e=>e.type===t.type)||globalThis.customStrategies.push(t)},ko=()=>{customElements.get(or)||customElements.define(or,Ge),customElements.get(nr)||customElements.define(nr,Pe),So({type:He,strategyType:"dashboard",name:ar,description:"What each device cost to run, and what solar and the battery saved."})};ko();var je=Object.keys(w),Ao=Object.keys(N),mr=t=>{let e=new Map;for(let r of t){if(!r.upstream)continue;let s=e.get(r.upstream);s?s.push(r):e.set(r.upstream,[r])}return e},Be=(t,e)=>({...t,key:`${t.key}${Oo}`,name:`${t.name} ${e.device_untracked}`,upstream:t.key,untracked:!1,gross:!1,residualOf:t.key}),Oo="__untracked",fr=(t,e)=>t.gross&&je.every(r=>!t[r])?[]:[Be(t,e)],To=t=>{let e=Object.fromEntries(je.map(r=>[r,0]));for(let r of t)for(let s of je)e[s]+=r[s]??0;for(let r of Ao)e[r]=t.every(s=>typeof s[r]=="number")?t.reduce((s,o)=>s+o[r],0):void 0;return e.costSavings=e.costAtGridPrice-e.actualCost,e},be=(t,e)=>{let r=mr(t);return r.size===0?t:t.flatMap(s=>r.has(s.key)?fr(s,e):[s])},_r=(t,e,r=s=>s)=>{let s=mr(t);if(s.size===0)return r(t).map(n=>({device:n,depth:0}));let o=(n,a)=>{if(!s.has(n.key))return[{device:n,depth:a}];let c=r([...s.get(n.key),...fr(n,e)]).flatMap(d=>o(d,a+1)),l=c.filter(d=>!d.device.subtotal).map(d=>d.device);return[{device:{...n,...To(l),subtotal:!0},depth:a},...c]};return r(t.filter(n=>!n.upstream)).flatMap(n=>o(n,0))};var F=Object.freeze(["#0072b2","#e69f00","#009e73","#cc79a7","#56b4e9","#d55e00","#8c6bb1","#3d9970"]),Co=Object.freeze(["#4b46b3","#8d9b1f","#00a2ab","#b07ad2","#7fa0ee","#a8761b","#b26596","#5b8f3f"]),Ue=Object.freeze([F,Co]),$a=F.length*Ue.length,q=Object.freeze({variable:"--secondary-text-color",fallback:"#8a8a8a"}),V=t=>{let e=(t??[]).filter(r=>!r.untracked).map(r=>r.key).sort($o);return new Map(e.map((r,s)=>{let o=Math.floor(s/F.length)%Ue.length;return[r,Ue[o][s%F.length]]}))},$o=(t,e)=>t===e?0:t<e?-1:1;var ve=(t,e,r)=>{let s=t<0?e.lost_share:e.saved_share;return v(s,{percent:K(Math.abs(t),r)})},Fo=({costSavings:t,costAtGridPrice:e})=>{if(!(!Number.isFinite(t)||!Number.isFinite(e))&&!(e<=0))return t/e},se=[{at:0,hue:3,light:48,dark:62},{at:.5,hue:35,light:46,dark:68},{at:1,hue:142,light:31,dark:76}],gr={light:85,dark:70},Ro=.7,yr=(t,e,r)=>t+(e-t)*r,Io=.6,No=(t,e)=>{let r=se.findIndex(i=>t<=i.at);if(r<=0)return{hue:se[0].hue,lightness:se[0][e]};let s=se[r-1],o=se[r],n=(t-s.at)/(o.at-s.at),a=r===1?n:n**Io;return{hue:yr(s.hue,o.hue,a),lightness:yr(s[e],o[e],n)}},br=.05,P=t=>Math.round(t*10)/10,xe=(t,{dark:e=!1}={})=>{let r=e?"dark":"light",s=n=>Math.max(0,n?.costAtGridPrice??0),o=Math.max(0,...(t??[]).map(s));return n=>{let a=Fo(n??{});if(a===void 0||o<=0)return;let i=Math.min(1,s(n)/o),c=i*(1+br)/(i+br),l=Math.min(1,Math.max(0,a)),{hue:d,lightness:h}=No(l,r),m=gr[r]*c**Ro;return{rate:a,text:`hsl(${P(d)}, ${P(m)}%, ${P(h)}%)`,edge:`hsla(${P(d)}, ${P(gr[r])}%, ${P(h)}%, ${P(c)})`}}};var Ar="hea-device-costs-card",Or=`${Ar}-editor`,vr={variable:"--error-color",fallback:"#db4437"},Do={variable:"--secondary-text-color",fallback:"#727272"},Lo="earlier-period",Mo=["auto","vertical","horizontal"],Go="paid",We="saved",xr="before",Po=30,Ho=46,jo=64,Bo=240,Uo=24,Wo=12,zo=2,Ko=10,Yo=300,qo=120,Vo="40vw",Zo={left:8,right:16,top:8,bottom:28,containLabel:!0},wr=1.5,Er=.8,Sr=.45,kr=.22,Xo=/:(?:paid|saved|before)$/,Qo={gain:{variable:"--success-color",fallback:"#4caf50"},loss:{variable:"--error-color",fallback:"#db4437"}},Jo=(t,e,r,s,o,n,a)=>{let i=document.createElement("div");if(i.append(_e(e),D(s.paid,u(t.actualCost,r))),!a){let d=k(t.costSavings,r);i.append(D(t.costSavings<0?s.lost:s.saved,u(t.costSavings,r),d?o(d):void 0),D(s.would_have_paid,u(t.costAtGridPrice,r)));let h=en(n,r,s);h&&i.append(h)}let c=tn(t,r,s,o);c&&i.append(c);let l=rn(t,r,s);return l&&i.append(l),i},en=(t,e,r)=>{if(!t)return;let s=document.createElement("div");return s.style.marginTop="4px",s.style.color=t.text,s.textContent=ve(t.rate,r,e),s},tn=(t,e,r,s)=>{let o=t.before?.actualCost;if(!Number.isFinite(o)||!Number.isFinite(t.actualCost))return;let n=t.actualCost-o,a=W("actualCost",n,e);return D(r.change,v(r.compared,{change:U(n,e),before:u(o,e)}),a?s(a):void 0)},rn=({costFloor:t,costCeiling:e},r,s)=>{if(![t,e].every(n=>Number.isFinite(n)))return;let o=document.createElement("div");return o.style.marginTop="4px",o.style.opacity="0.75",o.textContent=v(s.range_device,{range:z([t,e],r)}),o},ze=class extends ${static titleKey="title_device_costs";static narrowQuery=M;static getConfigElement(){return document.createElement(Or)}_isEmpty(){return this._ranked().every(e=>!e.costAtGridPrice&&!e.actualCost)}_ranked(){return be(this._result?.devices??[],this._labels).sort((e,r)=>r.actualCost-e.actualCost||e.name.localeCompare(r.name))}_colourFor(e){if(e.untracked)return this._colour(q);let r=e.residualOf??e.key;return this._colours().get(r)??F[0]}_colours(){return V(g(this._hass))}_verdicts(){return xe(this._ranked(),{dark:pe(this)})}_sideways(){let e=this._config?.layout;return e==="horizontal"?!0:e==="vertical"?!1:this._isNarrow()}_comparing(){return this._ranked().some(e=>e.before)}_series(){let e=this._sideways()?this._sidewaysSeries():this._standingSeries();return ie(this._result?.gridOnly?e.filter(({id:r})=>r!==We&&!r.endsWith(`:${We}`)):e)}_sidewaysSeries(){let e=this._ranked(),r=this._colour(vr),s=this._labels,o=n=>this._colourFor(n);return[{id:Go,name:s.paid,type:"bar",stack:"cost",data:e.map(n=>({value:n.actualCost,itemStyle:{color:I(o(n),Er)}}))},{id:We,name:s.saved,type:"bar",stack:"cost",data:e.map(n=>{let a=n.costSavings<0?r:o(n);return{value:n.costSavings,itemStyle:{color:I(a,kr),borderColor:a,borderWidth:wr}}})},...this._comparing()?[{id:xr,name:s.compared_series,type:"bar",stack:"earlier",data:e.map(n=>({value:n.before?n.before.actualCost:null,itemStyle:{color:I(o(n),Sr)}}))}]:[]]}_standingSeries(){let e=this._colour(vr);return this._ranked().flatMap(r=>{let s=this._colourFor(r),o=r.costSavings<0?e:s,n=r.name;return[{id:`${r.key}:paid`,name:n,type:"bar",stack:r.key,itemStyle:{color:I(s,Er)},data:[r.actualCost]},{id:`${r.key}:saved`,name:n,type:"bar",stack:r.key,itemStyle:{color:I(o,kr),borderColor:o,borderWidth:wr},data:[r.costSavings]},...r.before?[{id:`${r.key}:before`,name:n,type:"bar",stack:`${r.key}:before`,itemStyle:{color:I(s,Sr)},data:[r.before.actualCost]}]:[]]})}_tooltipFor({seriesId:e,dataIndex:r},s){let o=this._ranked(),n=this._sideways()?o[r]:o.find(a=>a.key===String(e??"").replace(Xo,""));return n?Jo(n,n.name,s,this._labels,a=>this._colour(Qo[a]),this._verdicts()(n),this._result?.gridOnly):void 0}_earlierKey(){if(!this._comparing())return[];let e=this._labels.compared_series,r={color:this._colour(Do)};return this._sideways()?[{id:xr,name:e,itemStyle:r}]:[{id:Lo,secondaryIds:this._ranked().filter(s=>s.before).map(s=>`${s.key}:before`),name:e,itemStyle:r}]}_chartHeight(){if(this._sideways()){let r=this._ranked().length,s=this._comparing()?Ho:Po;return`${Math.max(Bo,jo+r*s)}px`}let e=Yo+this._legendHeight();return`clamp(${e}px, ${Vo}, ${e+qo}px)`}_legendHeight(){let e=Math.min(this._ranked().length,Ko)+this._earlierKey().length;return Math.ceil(e/zo)*Uo+Wo}_options(e){return this._sideways()?this._sidewaysOptions(e):this._standingOptions(e)}_sidewaysOptions(e){let r=this._earlierKey();return{xAxis:{type:"value",name:J(e),axisLabel:{formatter:s=>Q(s,e),hideOverlap:!0}},yAxis:{type:"category",data:this._ranked().map(s=>s.name),inverse:!0},grid:Zo,tooltip:{trigger:"item",formatter:s=>this._tooltipFor(s,e)},...r.length?{legend:{show:!0,type:"custom",data:r}}:{}}}_standingOptions(e){return{xAxis:{type:"category",data:[ee(this._period,e)]},yAxis:{type:"value",name:J(e),nameGap:2,nameTextStyle:{align:"left"},axisLabel:{formatter:r=>Q(r,e),hideOverlap:!0}},tooltip:{trigger:"item",formatter:r=>this._tooltipFor(r,e)},legend:{show:!0,type:"custom",data:[...this._ranked().map(r=>({id:`${r.key}:paid`,secondaryIds:[`${r.key}:saved`,...r.before?[`${r.key}:before`]:[]],name:r.name,itemStyle:{color:this._colourFor(r)}})),...this._earlierKey()]}}}},Ke=class extends p{_extraSchema(){return[{name:"layout",selector:{select:{mode:"dropdown",options:Mo}}}]}},sn=()=>{_(Or,Ke),f(Ar,ze,{name:"Home Energy Advisor: Device costs (chart)",description:"What each device cost over the selected period, dearest first."})};sn();var on=`${me}
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
`,nn=(t,e,r,s)=>(t==="costSavings"?k(r,s):W(e,r,s))??"",Ye=({classes:t=[],styles:e=[]})=>{let r=t.filter(Boolean),s=e.filter(Boolean);return(r.length?` class="${r.join(" ")}"`:"")+(s.length?` style="${s.join("; ")}"`:"")},Tr=t=>t?`box-shadow: inset ${an} 0 0 ${t.edge}`:"",an="4px",H=class extends O{static columns=[];static sorts={};static defaultSort="";static cardStyle=on;setConfig(e){let{sorts:r}=this.constructor;if(e.sort_by!==void 0&&!(e.sort_by in r))throw new Error(`\`sort_by\` must be one of: ${Object.keys(r).join(", ")}`);super.setConfig(e)}getCardSize(){return 3+Math.ceil((this._result?.devices.length??3)/2)}_columns(){return this.constructor.columns}_body(e){let r=this._columns(),s=this._verdictScale();return`
      <div class="scroll">
        <table>
          <thead><tr>${r.map(o=>this._heading(o,e)).join("")}</tr></thead>
          <tbody>${this._ranked().map(({device:o,depth:n})=>this._row(o,e,s,n)).join("")}</tbody>
          <tfoot>${this._total(e,s)}</tfoot>
        </table>
      </div>`}_verdictScale(){if(this._columns().some(e=>e.carriesVerdict))return xe(this._result?.devices??[],{dark:pe(this)})}_heading({label:e},r){let s=this._labels;if(typeof e!="function")return`<th>${fe(e)}${s[e]}</th>`;let{text:o,unit:n}=e(r,s);return`<th>${o} <span class="unit">${b(n)}</span></th>`}_rank(e){let{sorts:r,defaultSort:s}=this.constructor,{field:o}=r[this._config?.sort_by??s];return[...e].sort((n,a)=>a[o]-n[o]||n.name.localeCompare(a.name))}_ranked(){return _r(this._result?.devices??[],this._labels,e=>this._rank(e))}_row(e,r,s,o){return`<tr${e.subtotal?' class="subtotal"':""}>${this._columns().map(a=>this._cell(a,e,r,s?.(e),o)).join("")}</tr>`}_cell(e,r,s,o,n){let{field:a,derive:i,format:c,reveal:l}=e;if(!c)return`<th scope="row"${Ye({classes:[n?"inside":""],styles:[n?`--depth: ${n}`:"",Tr(o)]})}>${b(r.name)}</th>`;let d=i?i(r):r[a],h=this._revealed(c(d,s),l?.(r,s,this._labels));return`<td${this._figureAttributes(e,d,o,s)}>${h}</td>`}_figureAttributes({field:e,tone:r,muted:s,carriesVerdict:o},n,a,i){let c=o?this._verdictOn(a,i):null;return Ye({classes:[nn(e,r,n,i),s?"muted":""],styles:[c?.style]})+(c?` title="${b(c.title)}"`:"")}_revealed(e,r){return r?`<span class="reveal" tabindex="0" aria-label="${b(r.label)}">${e}<span class="revealed" aria-hidden="true">${b(r.text)}</span></span>`:e}_total(e,r){let s=this._sumOfShown(),o=r?.(s);return`<tr>${this._columns().map(a=>{let{field:i,derive:c,format:l}=a;if(!l)return`<th scope="row"${Ye({styles:[Tr(o)]})}>${this._labels.total}</th>`;let d=c?c(s):s[i];return`<td${this._figureAttributes(a,d,o,e)}>${l(d,e)}</td>`}).join("")}</tr>`}_verdictOn(e,r){return e?{style:`color: ${e.text}`,title:ve(e.rate,this._labels,r)}:null}_sumOfShown(){let e=[...new Set(this._columns().flatMap(({field:a,fields:i,derive:c,format:l})=>l?c?i??[]:a?[a]:[]:[]))],r=be(this._result?.devices??[],this._labels),s=Object.fromEntries(this._columns().flatMap(({fields:a,field:i,readField:c})=>c?(a??[i]).map(l=>[l,c]):[])),o=a=>r.reduce((i,c)=>{for(let l of e){let d=a(c);i[l]+=s[l]?s[l](d,l):d[l]}return i},Object.fromEntries(e.map(i=>[i,0]))),n=o(a=>a);return r.length>0&&r.every(a=>a.before)&&(n.before=o(a=>a.before)),n}},we=(t,e)=>[{name:"sort_by",selector:{select:{mode:"dropdown",options:Object.entries(t).map(([r,{label:s}])=>({value:r,label:e[s]}))}}}];var $r="hea-devices-card",Fr=`${$r}-editor`,cn=({actualCost:t,energyUsed:e})=>e>0?t/e:void 0,Rr=t=>Object.values(N).every(e=>e in(t.statistics??{})),Ir=t=>({field:t,fields:[t],derive:e=>!e.statistics||te(e)?e[t]:void 0}),Nr={...Ir("costAtGridPrice"),label:"would_have_paid",format:u,muted:!0},Dr={...Ir("costSavings"),label:"saved",format:u},oe={fields:["costFloor","costCeiling"],derive:({costFloor:t,costCeiling:e})=>[t,e],label:"range_column",format:z,readField:(t,e)=>Number.isFinite(t[e])?t[e]:t.actualCost},Lr={fields:["actualCost"],derive:({actualCost:t,before:e})=>e&&Number.isFinite(t)&&Number.isFinite(e.actualCost)?t-e.actualCost:void 0,label:"change",format:U,tone:"actualCost"},Ee={field:"actualCost",label:"paid",format:u,carriesVerdict:!0,reveal:(t,e)=>{if(!Rr(t)||!oe.fields.every(s=>Number.isFinite(t[s])))return null;let r=z(oe.derive(t),e);return{text:r,label:`${u(t.actualCost,e)} (${r})`}}},Mr={field:"forgoneExport",label:"forgone_column",format:u,muted:!0},Cr=[{field:"name",label:"device"},{field:"energyUsed",label:"energy",format:R},Ee,Lr,oe,Nr,Dr,Mr,{derive:cn,label:(t,e)=>({text:e.rate,unit:At(t)}),format:Ot}],Gr={actual_cost:{field:"actualCost",label:"paid"},cost_at_grid_price:{field:"costAtGridPrice",label:"would_have_paid"},cost_savings:{field:"costSavings",label:"saved"},energy_used:{field:"energyUsed",label:"energy_used"}},qe=class extends H{static titleKey="title_devices";static columns=Cr;static sorts=Gr;static defaultSort="actual_cost";static narrowQuery=M;static cardStyle=`${H.cardStyle}
    .disclosure {
      margin-top: var(--hea-space-m);
      color: var(--secondary-text-color);
      font-size: 0.8em;
    }
  `;static getConfigElement(){return document.createElement(Fr)}_columns(){let e=this._rangeAsColumn(),r=new Set;e||r.add(oe),this._showsForgone()||r.add(Mr),this._hasComparison()||r.add(Lr);let s=!!this._result?.gridOnly;return s&&(r.add(Nr),r.add(Dr)),Cr.filter(o=>!r.has(o)).map(o=>{if(o!==Ee)return o;let n=e?{...Ee,reveal:void 0}:Ee;return s?{...n,carriesVerdict:!1}:n})}_rangeAsColumn(){let e=this._config?.range;return(e==="column"||e!=="rollover"&&!this._isNarrow())&&this._hasEveryBound()}_showsForgone(){return this._hasForgone()&&!this._isNarrow()}_hasComparison(){return(this._result?.devices??[]).some(e=>e.before)}_hasForgone(){return(this._result?.devices??[]).some(e=>(e.forgoneExport??0)>0)}_hasEveryBound(){let e=(this._result?.devices??[]).filter(Rr);return e.length>0&&e.every(r=>oe.fields.every(s=>Number.isFinite(r[s])))}_body(e){return`${super._body(e)}${this._disclosure(e)}`}_disclosure(e){let r=[this._rangeDisclosure(e),this._forgoneNote()].filter(Boolean);return r.length?`<div class="disclosure">${r.join(" ")}</div>`:""}_forgoneNote(){return this._hasForgone()?this._showsForgone()?this._labels.forgone_note:this._labels.forgone_hidden_note:""}_rangeDisclosure(e){if(this._hasEveryBound())return this._rangeNote();let r=this._result?.wholeHome;if(!r)return"";let s=z([r.costFloor,r.costCeiling],e);return v(this._labels.range_whole_home,{range:s})}_rangeNote(){return this._rangeAsColumn()?this._labels.range_note:this._labels.range_note_rollover}},Ve=class extends p{_extraSchema(){let e=x(this._hass);return[...we(Gr,e),{name:"range",selector:{select:{mode:"dropdown",options:[{value:"auto",label:e.editor_range_auto},{value:"rollover",label:e.editor_range_rollover},{value:"column",label:e.editor_range_column}]}}}]}},ln=()=>{_(Fr,Ve),f($r,qe,{name:"Home Energy Advisor: Devices",description:"Every tracked device over the selected period, ordered by what it cost."})};ln();var ne="household",Z=Object.freeze({source:0,household:1,floor:2,area:3,device:4}),Pr=Object.freeze({cost:{field:"actualCost",sources:null},energy:{field:"energyUsed",sources:[{id:"grid",field:"energyFromGrid",variable:"--energy-grid-consumption-color",fallback:"#488fc2"},{id:"generation",field:"energyFromGeneration",variable:"--energy-solar-color",fallback:"#ff9800"},{id:"battery",field:"energyFromBattery",variable:"--energy-battery-out-color",fallback:"#4db6ac"}]}}),dn=t=>{let e=V(t);return r=>r.untracked?q.fallback:e.get(r.key)??F[0]},un=({fallback:t})=>t,Ur=(t,e,{metric:r="cost",colour:s=un,deviceColour:o=dn(t),groupByFloor:n=!0,groupByArea:a=!0}={})=>{let{field:i,sources:c}=Pr[r]??Pr.cost,l=hn(t,i).filter(y=>y.value>0);if(l.length===0)return{nodes:[],links:[]};let d=l.reduce((y,ls)=>y+ls.value,0),h=mn(l,{groupByFloor:n,groupByArea:a}),m=fn(l,e,o),S=_n(c,t.filter(y=>y[i]>0),e,s);return{nodes:[...S,{id:ne,label:e.household,value:d,index:Z.household},...h.nodes,...m.nodes],links:[...S.map(y=>({source:y.id,target:ne,value:y.value})),...h.links,...m.links]}},hn=(t,e)=>{let r=new Map(t.map(a=>[a.key,a])),s=new Map,o=[];for(let a of t){let i=pn(a,r);i?s.has(i.key)?s.get(i.key).push(a):s.set(i.key,[a]):o.push(a)}let n=a=>{let i=Math.max(a[e]??0,0),c=(s.get(a.key)??[]).map(n).filter(l=>l.value>0);return{device:a,own:i,inside:c,value:c.reduce((l,d)=>l+d.value,i)}};return o.map(n)},pn=(t,e)=>{let r=e.get(t.upstream);if(!r)return null;let s=new Set;for(let o=r;o;o=e.get(o.upstream)){if(o.key===t.key)return null;if(s.has(o.key))break;s.add(o.key)}return r},mn=(t,{groupByFloor:e,groupByArea:r})=>{let s=new Map,o=new Map,n=[];return t.forEach(({device:a,value:i})=>{let c=e&&a.floorId?Hr(s,a.floorId,a.floorName):null,l=r&&a.areaId?Hr(o,a.areaId,a.areaName):null;c&&(c.value+=i),l&&(l.value+=i,l.floorId??=c?.id??null),n.push({source:gn(l,c),target:j(a),value:i})}),{nodes:[...Br(s,"floor_",Z.floor),...Br(o,"area_",Z.area)],links:[...yn(s,o),...n]}},fn=(t,e,r)=>{let s=Z.device+Wr(t),o=[],n=[],a=(i,c)=>{let{device:l,own:d,inside:h,value:m}=i,S=h.length>0;if(o.push({id:j(l),label:l.name,value:m,index:S?Z.device+c:s,color:r(l),...jr(l)}),!!S&&(h.forEach(y=>{n.push({source:j(l),target:j(y.device),value:y.value}),a(y,c+1)}),d>0)){let y=Be(l,e);o.push({id:j(y),label:y.name,value:d,index:s,color:r(l),...jr(l)}),n.push({source:j(l),target:j(y),value:d})}};return t.forEach(i=>a(i,0)),{nodes:o,links:n}},Wr=t=>t.reduce((e,r)=>r.inside.length>0?Math.max(e,1+Wr(r.inside)):e,0),j=t=>`device_${t.key}`,_n=(t,e,r,s)=>(t??[]).map(o=>({id:`source_${o.id}`,label:r[o.id],value:e.reduce((n,a)=>n+(a[o.field]??0),0),index:Z.source,color:s(o)})).filter(o=>o.value>0),Hr=(t,e,r)=>(t.has(e)||t.set(e,{id:e,name:r||e,value:0}),t.get(e)),gn=(t,e)=>t?`area_${t.id}`:e?`floor_${e.id}`:ne,jr=t=>{let e=t.statistics?.actual_cost;return e?{entityId:e}:{}},Br=(t,e,r)=>[...t.values()].map(s=>({id:`${e}${s.id}`,label:s.name,value:s.value,index:r})),yn=(t,e)=>[...[...t.values()].map(r=>({source:ne,target:`floor_${r.id}`,value:r.value})),...[...e.values()].map(r=>({source:r.floorId?`floor_${r.floorId}`:ne,target:`area_${r.id}`,value:r.value}))];var zr="hea-distribution-card",Kr=`${zr}-editor`,ae={cost:{titleKey:"title_distribution",emptyKey:"no_cost_in_period",format:u},energy:{titleKey:"title_distribution_energy",emptyKey:"no_energy_in_period",format:R}},bn="400px",vn=88,xn=240,wn=["auto","horizontal","vertical"],Ze=Object.freeze({group_by_floor:!0,group_by_area:!0}),Xe=class extends ${static titleKey="title_distribution";static chartTag="ha-sankey-chart";static bearingCard={type:"energy-sankey"};static narrowQuery=M;static cardStyle=`
    ha-sankey-chart { display: block; min-height: 240px; }
  `;static getConfigElement(){return document.createElement(Kr)}_isEmpty(){return this._layout().nodes.length===0}_verticalHeight({nodes:e}){let r=new Set(e.map(s=>s.index)).size;return`${Math.max(xn,r*vn)}px`}_metric(){return ae[this._config?.metric]?this._config.metric:"cost"}_titleKey(){return ae[this._metric()].titleKey}_emptyKey(){return ae[this._metric()].emptyKey}_layout(){let e=V(g(this._hass));return Ur(this._result?.devices??[],this._labels,{metric:this._metric(),groupByFloor:this._config?.group_by_floor??Ze.group_by_floor,groupByArea:this._config?.group_by_area??Ze.group_by_area,colour:r=>this._colour(r),deviceColour:r=>r.untracked?this._colour(q):e.get(r.key)??F[0]})}_chartMarkup(){return"<ha-sankey-chart></ha-sankey-chart>"}_draw(e){e.data=this._layout(),e.vertical=this._isVertical(),e.style.height=this._isVertical()?this._verticalHeight(e.data):bn;let r=this._chartLocale(),{format:s}=ae[this._metric()];e.valueFormatter=o=>s(o,r),this.toggleAttribute("data-vertical",e.vertical)}_isVertical(){let e=this._config?.layout;return e==="vertical"?!0:e==="horizontal"?!1:this._isNarrow()}},Qe=class extends p{_extraSchema(){return[{name:"metric",selector:{select:{mode:"dropdown",options:Object.keys(ae)}}},{name:"layout",selector:{select:{mode:"dropdown",options:wn}}},{name:"group_by_floor",selector:{boolean:{}}},{name:"group_by_area",selector:{boolean:{}}}]}setConfig(e){super.setConfig({...Ze,...e})}},En=()=>{_(Kr,Qe),f(zr,Xe,{name:"Home Energy Advisor: Cost distribution",description:"Where the period's cost went, by floor, room, circuit and device."})};En();var Yr="hea-filter-card",qr=`${Yr}-editor`,Sn=[{kind:"area",label:"filter_rooms",id:"areaId",name:"areaName"},{kind:"floor",label:"filter_floors",id:"floorId",name:"floorName"}],B=({kind:t,id:e})=>`${t}:${e??""}`,kn=t=>{let[e,r]=[t.slice(0,t.indexOf(":")),t.slice(t.indexOf(":")+1)];return{kind:e,id:r===""?null:r}},Je=class extends HTMLElement{constructor(){super(),this.attachShadow({mode:"open"})}setConfig(e){this._config=e,this._render()}set hass(e){this._hass=e,A(e).then(()=>this._renderIfChanged()),this._renderIfChanged()}getCardSize(){return 1}static getConfigElement(){return document.createElement(qr)}connectedCallback(){this._render(),this._unfilter??=de(this._config?.collection_key,()=>this._renderIfChanged())}_signature(){return JSON.stringify([this._allDevices().map(e=>[e.key,e.name,e.areaId,e.areaName,e.floorId,e.floorName,e.labels]),B(X(this._config?.collection_key)),this._labels.filter_rooms])}_renderIfChanged(){this._signature()!==this._drawn&&this._render()}disconnectedCallback(){this._unfilter?.(),this._unfilter=null}get _labels(){return x(this._hass)}_devices(){return g(this._hass).filter(e=>!e.untracked)}_allDevices(){return g(this._hass)}_optionsFor({kind:e,id:r,name:s},o){let n=new Map,a=!1;for(let c of o)c[r]?n.set(c[r],c[s]??c[r]):a=!0;let i=[...n.entries()].map(([c,l])=>({value:B({kind:e,id:c}),text:l})).sort((c,l)=>c.text.localeCompare(l.text));return a&&i.push({value:B({kind:e,id:null}),text:this._labels.filter_unfiled}),i}_labelOptions(e){let r=ft(this._hass);return[...new Set(e.flatMap(o=>o.labels??[]))].map(o=>({value:B({kind:"label",id:o}),text:r[o]??o})).sort((o,n)=>o.text.localeCompare(n.text))}_deviceOptions(){return this._allDevices().map(e=>({value:B({kind:"device",id:e.key}),text:e.name})).sort((e,r)=>e.text.localeCompare(r.text))}_groups(){let e=this._devices(),r=Sn.map(o=>({label:this._labels[o.label],options:this._optionsFor(o,e)})),s=this._labelOptions(e);return s.length&&r.push({label:this._labels.filter_labels,options:s}),r.push({label:this._labels.filter_devices,options:this._deviceOptions()}),r.filter(o=>o.options.length>0)}_render(){let e=this._labels,r=this._devices();this._drawn=this._signature();let s=r.length?this._control(e):`<p class="message">${e.no_devices}</p>`;this.shadowRoot.innerHTML=`
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
    `;let o=this.shadowRoot.querySelector("select");o&&(o.value=B(X(this._config?.collection_key)),o.addEventListener("change",()=>yt(this._config?.collection_key,kn(o.value))))}_control(e){let r=this._groups().map(s=>`<optgroup label="${b(s.label)}">${s.options.map(o=>`<option value="${b(o.value)}">${b(o.text)}</option>`).join("")}</optgroup>`).join("");return`<div class="body">
      <span class="label">${e.title_filter}</span>
      <select>
        <option value="${B({kind:"all",id:null})}">${b(e.filter_everything)}</option>
        ${r}
      </select>
    </div>`}},et=class extends p{},An=()=>{_(qr,et),f(Yr,Je,{name:"Home Energy Advisor: Filter",description:"Narrow every Home Energy Advisor card on the page to a room, a floor, a label or one device."})};An();var Vr="hea-installation-card",Zr=`${Vr}-editor`,On=[{key:"generationSaved",label:"generation_saved"},{key:"batterySaved",label:"battery_saved"},{key:"exportsEarned",label:"exports_earned"}],tt=class extends O{static titleKey="title_installation";static cardStyle=`
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
  `;static getConfigElement(){return document.createElement(Zr)}getCardSize(){return 4}async _fetch(){if(!this._hass||!this._period)return;let e=++this._request;await A(this._hass);let r=L(this._hass);if(!re(this._hass,r)){this._state="empty",this._render();return}try{let s={...er(r,g(this._hass)),exportsEarned:await this._exportStatistics()},o=await this._hass.callWS({type:"recorder/statistics_during_period",start_time:this._period.start.toISOString(),end_time:this._period.end.toISOString(),statistic_ids:rr(s),period:C(this._period),types:["change"]});if(e!==this._request)return;this._earned=sr(o,s,this._period),this._state="ready"}catch(s){if(e!==this._request)return;this._state="error",console.error(`${this.localName}: could not load statistics`,s)}this._render()}async _exportStatistics(){try{let[e,r]=await Promise.all([this._hass.callWS({type:"energy/get_prefs"}),this._hass.callWS({type:"energy/info"})]);return tr(e,r)}catch{return[]}}_content(e){return this._state==="empty"?`<p class="message">${this._labels.no_installation}</p>`:super._content(e)}_body(e){let r=this._earned;return`
      <div class="parts">
        ${On.filter(({key:o})=>r?.[o]!==void 0).map(({key:o,label:n})=>this._line("part",o,this._labels[n],e)).join("")}
        ${this._line("total","total",this._labels.total,e)}
      </div>
      <div class="hint">${this._labels.installation_note}</div>`}_line(e,r,s,o){let n=this._earned?.[r],a=k(n,o);return`
      <div class="${e}">
        <span class="label">${s}</span>
        <span class="value${a?` ${a}`:""}" data-figure="${r}">${u(n,o)}</span>
      </div>`}},rt=class extends p{},Tn=()=>{_(Zr,rt),f(Vr,tt,{name:"Home Energy Advisor: What your installation earned",description:"What your generation, battery and exports earned over the selected period, for the whole home."})};Tn();var Xr="hea-plans-card",Qr=`${Xr}-editor`,Cn="home_energy_advisor/compare_plans",$n=[{key:"energy",label:"plans_energy",sign:1},{key:"export",label:"plans_export",figure:"export_credit",sign:-1},{key:"daily",label:"plans_daily",figure:"daily_charges",sign:1}],Fn=(t,e)=>t.incomplete||e.incomplete?(t.incomplete?1:0)-(e.incomplete?1:0):t.total-e.total,st=class extends O{static titleKey="title_plans";static cardStyle=`
    .plans { display: flex; flex-direction: column; gap: var(--hea-space-m); }
    .plan + .plan {
      padding-top: var(--hea-space-m);
      border-top: 1px solid var(--divider-color);
    }
    .head {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: var(--hea-space-m);
    }
    .name { color: var(--primary-text-color); font-weight: 500; }
    .tag {
      margin-inline-start: var(--hea-space-s);
      padding: 0 var(--hea-space-s);
      border-radius: var(--ha-border-radius-pill, 9px);
      background: var(--secondary-background-color);
      color: var(--secondary-text-color);
      font-size: 0.8em;
      font-weight: normal;
    }
    .total { font-size: 1.4em; white-space: nowrap; }
    .parts, .difference, .incomplete {
      color: var(--secondary-text-color);
      font-size: 0.9em;
    }
    .parts { display: flex; flex-wrap: wrap; gap: 0 var(--hea-space-m); }
    .part .value { color: var(--primary-text-color); white-space: nowrap; }
  `;static getConfigElement(){return document.createElement(Qr)}getCardSize(){return 5}async _fetch(){if(!this._hass||!this._period)return;let e=++this._request;await A(this._hass);try{let r=await this._hass.callWS({type:Cn,start_time:this._period.start.toISOString(),end_time:this._period.end.toISOString()});if(e!==this._request)return;this._compared=r,this._state=r?.plans?.length?"ready":"empty"}catch(r){if(e!==this._request)return;this._state="error",console.error(`${this.localName}: could not compare the plans`,r)}this._render()}_content(e){return this._state==="empty"?`<p class="message">${this._labels.no_plans}</p>`:super._content(e)}_body(e){if(!this._compared?.plans)return"";let r=[...this._compared.plans].sort(Fn),s=r.filter(i=>!i.incomplete),o=s.find(i=>i.current),n=s.length>1?s[0]:void 0,a=[this._compared.hours===0?this._labels.plans_no_readings:"",o?"":this._labels.plans_no_current,this._labels.plans_note].filter(Boolean);return`
      <div class="plans">
        ${r.map(i=>this._plan(i,{current:o,cheapest:n},e)).join("")}
      </div>
      ${a.map(Rn).join("")}`}_plan(e,{current:r,cheapest:s},o){let n=[e.current?this._labels.plans_your_plan:"",e===s?this._labels.plans_cheapest:""].filter(Boolean).map(c=>`<span class="tag">${c}</span>`).join(""),a=e.incomplete?"":this._total(e,o),i=`
      <div class="head">
        <span class="name">${In(e.name)}${n}</span>
        ${a}
      </div>`;return e.incomplete?`<div class="plan" data-plan="${e.id}">${i}
        <div class="incomplete">${this._labels.plans_incomplete}</div></div>`:`<div class="plan" data-plan="${e.id}">${i}
      <div class="parts">${$n.map(c=>this._part(e,c,o)).join("")}</div>
      ${r&&e!==r?this._difference(e,r,o):""}
    </div>`}_total(e,r){return`<span class="total" data-figure="total:${e.id}">${u(e.total,r)}</span>`}_part(e,{key:r,label:s,figure:o=r,sign:n},a){return`
      <span class="part">${this._labels[s]}
        <span class="value" data-figure="${r}:${e.id}">${u(n*e[o],a)}</span>
      </span>`}_difference(e,r,s){let o=r.total-e.total,n=k(o,s),a=u(Math.abs(o),s),i=this._labels.plans_same;return n==="gain"&&(i=v(this._labels.plans_less,{amount:a})),n==="loss"&&(i=v(this._labels.plans_more,{amount:a})),`<div class="${n?`difference ${n}`:"difference"}" data-figure="difference:${e.id}">${i}</div>`}},Rn=t=>`<div class="hint">${t}</div>`,In=t=>String(t).replaceAll(/[&<>"']/g,e=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[e]),ot=class extends p{},Nn=()=>{_(Qr,ot),f(Xr,st,{name:"Home Energy Advisor: Compare tariff plans",description:"What each tariff plan you have entered would have cost over the selected period, for the whole home."})};Nn();var ts="hea-self-sufficiency-card",rs=`${ts}-editor`,Jr=["energyUsed","energyFromGrid","energyFromGeneration","energyFromBattery","energyFromBatterySolar"],Dn={maximumFractionDigits:0},es=.005,nt=class extends ${static titleKey="title_self_sufficiency";static chartTag="ha-gauge";static bearingCard={type:"energy-self-sufficiency-gauge"};static emptyKey="no_energy_in_period";static cardStyle=`
    ha-gauge { display: block; margin: 0 auto; --gauge-color: var(--primary-color); }
    .headline {
      margin-top: var(--hea-space-s);
      text-align: center;
      color: var(--secondary-text-color);
      font-size: 0.85em;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    .shares {
      display: flex;
      flex-wrap: wrap;
      gap: var(--hea-space-l);
      margin-top: var(--hea-space-l);
    }
    .share {
      flex: 1 1 6em;
      display: flex;
      flex-direction: column;
      gap: var(--hea-space-xs);
    }
    .label {
      color: var(--secondary-text-color);
      font-size: 0.85em;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    .value { color: var(--primary-text-color); font-size: 1.2em; font-weight: 500; }
    .note {
      margin-top: var(--hea-space-m);
      color: var(--secondary-text-color);
      font-size: 0.8em;
    }
  `;static getConfigElement(){return document.createElement(rs)}getCardSize(){return 4}_isEmpty(){return this._totals().energyUsed<=0}_totals(){return(this._result?.devices??[]).reduce((e,r)=>{for(let s of Jr)e[s]+=r[s];return e},Object.fromEntries(Jr.map(e=>[e,0])))}_shares(){let e=this._totals(),r=e.energyUsed,s=c=>e[c]/r,o=s("energyFromBatterySolar"),n=s("energyFromGeneration")+o,a=s("energyFromBattery")-o,i=s("energyFromGrid");return{generation:n,storedSolar:o,battery:a,grid:i,unaccounted:Math.max(0,1-n-a-i)}}_body(e){let r=super._body(e);return!this._chartReady||this._isEmpty()?r:`${r}${this._breakdown(e)}`}_chartMarkup(){let e=this._shares().storedSolar>es?`<div class="headline">${this._labels.including_stored_solar}</div>`:"";return`<ha-gauge></ha-gauge>
      <div class="headline">${this._labels.from_generation}</div>${e}`}_breakdown(e){let{battery:r,grid:s,unaccounted:o}=this._shares();return`<div class="shares">${[{label:"from_battery_grid",value:r},{label:"from_grid",value:s},{label:"unaccounted",value:o}].filter(({label:a,value:i})=>a!=="unaccounted"||i>es).map(({label:a,value:i})=>`
        <div class="share">
          <span class="label">${this._labels[a]}</span>
          <span class="value" data-share="${a}">${K(i,e)}</span>
        </div>`).join("")}</div>
      <div class="note">${this._labels.self_sufficiency_note}</div>`}_draw(e){e.min=0,e.max=100,e.value=this._shares().generation*100,e.label="%",e.formatOptions=Dn,e.locale=this._hass?.locale}},at=class extends p{},Ln=()=>{_(rs,at),f(ts,nt,{name:"Home Energy Advisor: Self-sufficiency",description:"What share of the selected period's energy came from the household's own generation."})};Ln();var ss="hea-sources-card",os=`${ss}-editor`,Mn=({energyFromGrid:t,energyUsed:e})=>e>0&&t>=0&&t<=e?t/e:void 0,Gn=[{field:"name",label:"device"},{field:"energyUsed",label:"energy",format:R},{field:"energyFromGrid",label:"grid",format:R},{field:"energyFromGeneration",label:"generation",format:R},{field:"energyFromBattery",label:"battery",format:R},{derive:Mn,label:"from_grid",format:K}],ns={energy_used:{field:"energyUsed",label:"energy_used"},energy_from_grid:{field:"energyFromGrid",label:"from_grid"},energy_from_generation:{field:"energyFromGeneration",label:"from_generation"},energy_from_battery:{field:"energyFromBattery",label:"from_battery"}},it=class extends H{static titleKey="title_sources";static columns=Gn;static sorts=ns;static defaultSort="energy_used";static getConfigElement(){return document.createElement(os)}},ct=class extends p{_extraSchema(){return we(ns,x(this._hass))}},Pn=()=>{_(os,ct),f(ss,it,{name:"Home Energy Advisor: Energy sources",description:"Grid, generation and battery behind each device's energy over the period."})};Pn();var is="hea-totals-card",cs=`${is}-editor`,as=[{key:"actualCost",label:"paid"},{key:"costAtGridPrice",label:"would_have_paid"},{key:"costSavings",label:"saved"}],lt=class extends O{static titleKey="title_totals";static cardStyle=`${me}
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
  `;static getConfigElement(){return document.createElement(cs)}getCardSize(){return 3}_body(e){let r=this._result?.totals;return`<div class="figures">${(this._result?.gridOnly?as.slice(0,1):as).map(({key:n,label:a})=>{let i=r?.[n],c=n==="costSavings"?k(i,e):"",l=c?` ${c}`:"";return`
        <div class="figure">
          <span class="label">${fe(a)}${this._labels[a]}</span>
          <span class="value${l}" data-figure="${n}">${u(i,e)}</span>
          ${this._comparedTo(n,i,e)}
        </div>`}).join("")}</div>`}_comparedTo(e,r,s){let o=this._result?.totals?.before?.[e];if(!Number.isFinite(o)||!Number.isFinite(r))return"";let n=W(e,r-o,s);return`<span class="${n?`compare ${n}`:"compare"}" data-compare="${e}">${v(this._labels.compared,{change:U(r-o,s),before:u(o,s)})}</span>`}},dt=class extends p{},Hn=()=>{_(cs,dt),f(is,lt,{name:"Home Energy Advisor: Totals",description:"What the selected period cost, what it would have cost at grid price, and the difference."})};Hn();
