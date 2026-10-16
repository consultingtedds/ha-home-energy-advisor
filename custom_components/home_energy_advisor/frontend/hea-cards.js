var Fr=[4,4,0,0],Rr=[0,0,4,4],Qe=t=>t!==null&&typeof t=="object"&&!Array.isArray(t),$r=t=>{let e=Qe(t)?t.value:t;return Array.isArray(e)?e[1]:e},be=(t,e)=>{let r=Qe(t)?{...t}:{value:t};return{...r,itemStyle:{...r.itemStyle,...e}}},oe=t=>{let e=Math.max(...t.map(({data:o})=>o.length),0),r=t.map(({data:o})=>[...o]);for(let o of Nr(t))for(let s=0;s<e;s++)Ir(r,s,o);return t.map((o,s)=>({...o,data:r[s]}))},Nr=t=>{let e=new Map;return t.forEach((r,o)=>{let s=r.stack??Symbol(o),a=e.get(s);a?a.push(o):e.set(s,[o])}),[...e.values()]},Ir=(t,e,r)=>{let o=!1,s=!1;for(let a=r.length-1;a>=0;a--){let n=r[a],i=t[n][e];if(i===void 0)continue;let c=$r(i);c?c>0&&!o?(t[n][e]=be(i,{borderRadius:Fr}),o=!0):c<0&&!s&&(t[n][e]=be(i,{borderRadius:Rr}),s=!0):t[n][e]=be(i,{borderWidth:0})}};var Je="_energy",ve="energy_";var Dr=(t,e)=>{let r=t||(e?`${ve}${e}`:"");return r?r.startsWith(ve)?`_${r}`:`_${ve}${r}`:Je},Lr=(t,e)=>typeof t=="string"&&t.startsWith(Je)&&e!==null&&typeof e=="object"&&typeof e.subscribe=="function"&&"start"in e,Mr=(t=new Date)=>{let e=new Date(t);return e.setDate(e.getDate()-30),e.setHours(0,0,0,0),{start:e,end:t,fallback:!0}},Gr=t=>{let e=t?.connection;if(!e)return{};let r={};for(let o of Object.keys(e)){let s;try{s=e[o]}catch{continue}Lr(o,s)&&(r[o]=s)}return r},Hr=(t,e)=>{let r=Gr(t),o=Dr(e,t?.panelUrl);if(r[o])return r[o];let[s]=Object.values(r);return s??null},Pr=t=>t?.startCompare&&t?.endCompare?{compare:{start:t.startCompare,end:t.endCompare,mode:t.compareMode}}:{},et=(t,e,r)=>{let o=null,s=null,a=0,n=t,i=l=>{if(o)return!0;let d=Hr(l,e);if(!d)return!1;let m=x=>r({start:d.start,end:d.end,fallback:!1,...Pr(x)});return o=d.subscribe(m),m(),!0},c=()=>{s=setTimeout(()=>{s=null,a+=1,!i(n)&&a<40&&c()},250)};return r(Mr()),i(t)||c(),{retry:l=>(l&&(n=l),i(n)),unsubscribe:()=>{s&&clearTimeout(s),s=null;try{typeof o=="function"&&o()}catch{}o=null}}};var se="sensor.home_energy_advisor_devices",jr="home_energy_advisor",ne=t=>{if(t?.states?.[se])return se;let e=t?.entities;if(!e)return se;for(let[r,o]of Object.entries(e))if(o?.platform===jr&&Array.isArray(t?.states?.[r]?.attributes?.devices))return r;return se},y=(t,e=void 0)=>{let r=t?.states?.[e??ne(t)]?.attributes?.devices;return Array.isArray(r)?r.filter(o=>o?.key).map(st):[]},tt=(t,e=void 0)=>{let r=t?.states?.[e??ne(t)]?.attributes?.whole_home;return r?.key?st(r):null},rt=(t,e=void 0)=>{let r=t?.states?.[e??ne(t)]?.attributes?.settled_until;if(typeof r!="string")return null;let o=new Date(r);return Number.isNaN(o.getTime())?null:o},ot=(t,e=void 0)=>{let r=t?.states?.[e??ne(t)]?.attributes?.labels;return r&&typeof r=="object"?r:{}},st=t=>({key:t.key,name:t.name||t.key,deviceId:t.device_id??null,untracked:!!t.untracked,statistics:t.statistics??{},areaId:t.area_id??null,areaName:t.area_name??null,floorId:t.floor_id??null,floorName:t.floor_name??null,upstream:t.upstream??null,labels:Array.isArray(t.labels)?t.labels:[]});var nt=Object.freeze({kind:"all",id:null}),Ur={area:"areaId",floor:"floorId"},xe=new Map,we=t=>(xe.has(t)||xe.set(t,{filter:nt,listeners:new Set}),xe.get(t)),Y=t=>we(t).filter,ae=(t,e)=>{let{listeners:r}=we(t);return r.add(e),()=>r.delete(e)},at=(t,e)=>{let r=we(t),o={kind:e?.kind??"all",id:e?.id??null};if(!(o.kind===r.filter.kind&&o.id===r.filter.id)){r.filter=o;for(let s of r.listeners)try{s(o)}catch(a){console.warn("home-energy-advisor: a card could not follow the filter",a)}}},it=(t,e)=>{let{kind:r,id:o}=e??nt;if(r==="all")return!0;if(r==="device")return t.key===o;if(t.untracked)return!1;if(r==="label")return(t.labels??[]).includes(o);let s=Ur[r];return s?(t[s]??null)===o:!0};var Br={day:"numeric",month:"short",year:"numeric"},ie=t=>({language:t?.locale?.language||void 0,currency:t?.config?.currency||void 0,timeFormat:t?.locale?.time_format||void 0,timeZone:t?.locale?.time_zone==="server"?t?.config?.time_zone:void 0}),zr=({timeFormat:t,language:e})=>{if(t==="language"||t==="system"||!t){let r=t==="system"?void 0:e;return new Date("January 1, 2023 22:00:00").toLocaleString(r).includes("10")}return t==="12"},ct=(t,e)=>new Intl.DateTimeFormat(e.language,{hour:"numeric",minute:"2-digit",hourCycle:zr(e)?"h12":"h23",timeZone:e.timeZone}).format(t),Wr=(t,e)=>new Intl.DateTimeFormat(e.language,{weekday:"short",month:"short",day:"numeric",timeZone:e.timeZone}).format(t),Kr={hour:3600*1e3},lt=(t,e,r)=>{let o=Kr[e];if(!o)return Wr(t,r);let s=new Date(t.getTime()+o);return`${ct(t,r)} \u2013 ${ct(s,r)}`},u=(t,{language:e,currency:r})=>{if(typeof t!="number"||!Number.isFinite(t))return"-";let o=r?{style:"currency",currency:r}:{minimumFractionDigits:2,maximumFractionDigits:2};return new Intl.NumberFormat(e,o).format(t)},G=(t,{language:e,currency:r})=>{if(typeof t!="number"||!Number.isFinite(t))return"-";let o=r?{style:"currency",currency:r,signDisplay:"exceptZero"}:{minimumFractionDigits:2,maximumFractionDigits:2,signDisplay:"exceptZero"};return new Intl.NumberFormat(e,o).format(t)},Yr=new Set(["actualCost","costAtGridPrice","energyUsed"]),Vr=new Set(["costSavings"]),S=t=>typeof t!="number"||!Number.isFinite(t)||t===0?"":t>0?"gain":"loss",H=(t,e)=>typeof e!="number"||!Number.isFinite(e)||e===0?"":Yr.has(t)?e<0?"gain":"loss":Vr.has(t)?e>0?"gain":"loss":"",P=(t,e)=>{if(!Array.isArray(t))return"-";let[r,o]=t;if(![r,o].every(n=>Number.isFinite(n)))return"-";if(r===o)return u(r,e);let[s,a]=r<=o?[r,o]:[o,r];return`${u(s,e)} - ${u(a,e)}`},k=(t,{language:e})=>typeof t!="number"||!Number.isFinite(t)?"-":`${new Intl.NumberFormat(e,{maximumFractionDigits:1}).format(t)} kWh`,dt={EUR:{symbol:"c",per:100},USD:{symbol:"\xA2",per:100},GBP:{symbol:"p",per:100}},V=(t,{language:e})=>typeof t!="number"||!Number.isFinite(t)?"-":new Intl.NumberFormat(e,{minimumFractionDigits:t===0?0:2,maximumFractionDigits:2}).format(t),q=({language:t,currency:e})=>e?ut(t,e):"",ut=(t,e)=>new Intl.NumberFormat(t,{style:"currency",currency:e}).formatToParts(0).find(r=>r.type==="currency")?.value??"",ht=({language:t,currency:e})=>{if(!e)return"/kWh";let r=dt[e];return`${r?r.symbol:ut(t,e)}/kWh`},mt=(t,{language:e,currency:r})=>{if(typeof t!="number"||!Number.isFinite(t))return"-";let o=r?dt[r]:void 0;return new Intl.NumberFormat(e,{minimumFractionDigits:o?1:0,maximumFractionDigits:o?2:3}).format(o?t*o.per:t)},j=(t,{language:e})=>typeof t!="number"||!Number.isFinite(t)?"-":new Intl.NumberFormat(e,{style:"percent",maximumFractionDigits:0}).format(t),g=t=>String(t).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#39;"),Z=(t,{language:e})=>t?new Intl.DateTimeFormat(e,Br).formatRange(t.start,t.end):"";var ft="common",_t="home_energy_advisor",pt=`component.${_t}.${ft}.card_`,ke=Object.freeze({paid:"Paid",would_have_paid:"Would have paid",saved:"Saved",lost:"Lost",range_column:"Paid (min-max)",range_note:"Paid (min-max) is the widest range these readings allow, not a typical error: a meter that reports every 30-90 minutes leaves the exact moment of use unknown.",range_whole_home:"What you paid could honestly sit between {range} - the widest these readings allow, not a typical error.",range_device:"What you paid could be between {range}.",range_note_rollover:"Hover over or tap a figure in Paid to see the range it could honestly have been. That range is the widest these readings allow, not a typical error: a meter that reports every 30-90 minutes leaves the exact moment of use unknown.",forgone_column:"Could have earned",forgone_note:"Could have earned is what the generation each device used could have earned had you exported it instead, at your export rate at the time. It is money you did not receive, not money you paid, and it is not part of Paid.",forgone_hidden_note:"Could have earned, what the generation each device used could have earned had you exported it instead, is shown on a wider screen.",compared:"{change} vs {before}",compared_period:"{period} vs {compared}",saved_share:"{percent} of what you would have paid was saved.",lost_share:"{percent} more was paid than the grid would have cost.",change:"Change",compared_series:"Earlier period",device:"Device",energy:"Energy",rate:"Rate",total:"Total",grid:"Grid",generation:"Generation",battery:"Battery",from_grid:"From the grid",from_generation:"From generation",from_battery:"From the battery",energy_used:"Energy used",unaccounted:"Unaccounted",self_sufficiency_note:"Battery energy is counted on its own: it was charged from generation or from the grid, and these readings cannot say which.",household:"Household",title_totals:"Cost summary",title_devices:"Cost by device",title_device_costs:"What each device cost",title_cost_over_time:"Cost over time",title_sources:"Where the energy came from",title_self_sufficiency:"Self-sufficiency",title_distribution:"Where the cost went",title_distribution_energy:"Where the energy went",no_devices:"No devices are being tracked yet.",no_devices_in_filter:"No tracked device matches what the page is showing.",title_filter:"Show",filter_everything:"Everything",filter_rooms:"Rooms",filter_floors:"Floors",filter_labels:"Labels",filter_devices:"Devices",filter_unfiled:"Not in one",device_untracked:"Untracked",hourly_shape_estimate:"One device's hourly shape is an estimate: each meter reading is spread across the hours it spanned, so cost may not land in the hour the energy was used.",still_accruing:"The last interval is still being counted, so its bar will grow. Figures are complete about twenty minutes behind the clock, which is how long meters are given to report.",statistics_failed:"Statistics could not be loaded.",no_picker:"Add an Energy date picker card to choose the range.",chart_not_loaded:"Home Assistant's chart component is not loaded. Adding any energy or statistics card to this dashboard will load it.",no_cost_in_period:"No cost recorded in this period.",no_energy_in_period:"No energy recorded in this period.",editor_title:"Title",editor_collection_key:"Energy period (collection key)",editor_devices:"Devices (all, if none are chosen)",editor_sort_by:"Order by",editor_layout:"Layout",editor_metric:"Measure by",editor_group_by_floor:"Group by floor",editor_group_by_area:"Group by area",editor_range:"Show the cost range as",editor_range_auto:"Automatic: a column where there is room",editor_range_rollover:"A rollover on Paid",editor_range_column:"Its own column"}),Ee=new Map,gt=new Map,yt=t=>t?.locale?.language||t?.language||"en",T=t=>{let e=yt(t);return Ee.has(e)||Ee.set(e,qr(t,e).then(r=>(gt.set(e,r),r))),Ee.get(e)},qr=async(t,e)=>{try{let{resources:r}=await t.callWS({type:"frontend/get_translations",language:e,category:ft,integration:[_t]});return Object.freeze({...ke,...Zr(r)})}catch(r){return console.warn("home-energy-advisor: falling back to English labels",r),ke}},b=t=>gt.get(yt(t))??ke,Zr=t=>Object.fromEntries(Object.entries(t??{}).filter(([e,r])=>e.startsWith(pt)&&r).map(([e,r])=>[e.slice(pt.length),r])),v=(t,e)=>Object.entries(e).reduce((r,[o,s])=>r.replaceAll(`{${o}}`,s),t);var U=Object.freeze({energyUsed:"energy_used",actualCost:"actual_cost",costAtGridPrice:"cost_at_grid_price",energyFromGrid:"energy_from_grid",energyFromGeneration:"energy_from_generation",energyFromBattery:"energy_from_battery",forgoneExport:"forgone_export"}),O=Object.freeze({costFloor:"lowest_possible_cost",costCeiling:"highest_possible_cost"}),Ae=()=>Object.fromEntries(Object.keys(U).map(t=>[t,0])),xt=1440*60*1e3,wt={hour:3600*1e3,day:xt},Xr=2,X=(t,e)=>t?.statistics?.[e],Qr=(t,e)=>{let r=t.flatMap(o=>[...Object.values(U),...Object.values(O)].map(s=>X(o,s)).filter(Boolean));return!e?.statistics||t.length===0?r:[...r,...Object.values(O).map(o=>X(e,o)).filter(Boolean)]},Et=(t,e)=>{if(!e)return t;let r=new Map(e.devices.map(o=>[o.key,o]));return{...t,totals:{...t.totals,before:e.totals},devices:t.devices.map(o=>({...o,before:r.get(o.key)})),seriesBefore:Jr(e.series,t.period,e.period)}},Jr=(t,e,r)=>{if(!t?.length)return;let o=e.start.getTime()-r.start.getTime();return t.map(s=>({...s,start:new Date(s.start.getTime()+o),actualStart:s.start}))},C=({start:t,end:e})=>e-t>Xr*xt?"day":"hour",bt=(t,e,r)=>{if(e!=="day")return new Date(t.getTime()+r*wt.hour);let o=new Date(t);return o.setDate(o.getDate()+r),o},kt=(t,e)=>{if(!t.length||!e)return t;let r=C(e),o=new Map(t.map(n=>[n.start.getTime(),n])),s=t[0].start,a=[];for(let n=0;;n--){let i=bt(s,r,n);if(i.getTime()<e.start.getTime())break;a.push(o.get(i.getTime())??vt(i))}a.reverse();for(let n=1;;n++){let i=bt(s,r,n);if(i.getTime()>=e.end.getTime())break;a.push(o.get(i.getTime())??vt(i))}return a},vt=t=>({...Ae(),start:t,costSavings:0,accruing:!1}),Se=async(t,e,r,o,s=null)=>{let a=Qr(e,o),n=a.length?await t.callWS({type:"recorder/statistics_during_period",start_time:r.start.toISOString(),end_time:r.end.toISOString(),statistic_ids:a,period:C(r),types:["change"]}):{},i=e.map(c=>to(c,n,r));return{period:r,devices:i,totals:ro(i),wholeHome:At(o,n,r),series:eo(e,n,r,s)}},At=(t,e,r)=>{if(!t)return;let o={};for(let[s,a]of Object.entries(O)){let n=e?.[X(t,a)];if(!Array.isArray(n))return;o[s]=Tt(n,r)}return o},eo=(t,e,r,o)=>{let s=new Map;for(let n of t)for(let[i,c]of Object.entries(U)){let l=e?.[X(n,c)];for(let d of St(l,r)){let m=s.get(d.start)??Ae();m[i]+=d.change,s.set(d.start,m)}}let a=wt[C(r)]??0;return[...s.entries()].sort(([n],[i])=>n-i).map(([n,i])=>({...i,start:new Date(n),costSavings:i.costAtGridPrice-i.actualCost,accruing:o?n+a>o.getTime():!1}))},to=(t,e,r)=>{let o=Object.fromEntries(Object.entries(U).map(([s,a])=>[s,Tt(e?.[X(t,a)],r)]));return{...t,...o,...At(t,e,r),costSavings:o.costAtGridPrice-o.actualCost}},St=(t,{start:e,end:r})=>{if(!Array.isArray(t))return[];let o=[];for(let s of t){let a=new Date(s.start).getTime();a<e.getTime()||a>=r.getTime()||typeof s.change=="number"&&o.push({start:a,change:s.change})}return o},Tt=(t,e)=>St(t,e).reduce((r,o)=>r+o.change,0),ro=t=>({...t.reduce((r,o)=>{for(let s of Object.keys(r))r[s]+=o[s];return r},{...Ae(),costSavings:0}),...oo(t)}),oo=t=>{let e=Object.keys(O);return!t.length||!t.every(r=>e.every(o=>o in r))?{}:Object.fromEntries(e.map(r=>[r,t.reduce((o,s)=>o+s[r],0)]))};var so=`
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
`,no=`
  .loss { color: var(--error-color, #db4437); }
  .gain { color: var(--success-color, #4caf50); }
`,N="(max-width: 767px)",F=class extends HTMLElement{static cardStyle="";static narrowQuery="";static titleKey="";_titleKey(){return this.constructor.titleKey}get _labels(){return b(this._hass)}constructor(){super(),this.attachShadow({mode:"open"}),this._state="loading",this._request=0}setConfig(e){if(e.devices!==void 0&&!Array.isArray(e.devices))throw new Error("`devices` must be a list of device keys");this._config=e,this._render()}set hass(e){this._hass=e,this._subscription?this._subscription.retry(e):this._subscribe(),this._refetchIfDevicesChanged()}connectedCallback(){this._render(),this._hass&&!this._subscription&&this._subscribe(),this._watchScreen()}disconnectedCallback(){this._subscription?.unsubscribe(),this._subscription=null,this._unfilter?.(),this._unfilter=null,this._screen?.removeEventListener?.("change",this._onScreenChange),this._screen=null}_watchScreen(){let{narrowQuery:e}=this.constructor;!e||this._screen||(this._screen=globalThis.matchMedia?.(e),this._onScreenChange??=()=>this._render(),this._screen?.addEventListener?.("change",this._onScreenChange))}_isNarrow(){return!!globalThis.matchMedia?.(N)?.matches}_subscribe(){this._subscription=et(this._hass,this._config?.collection_key,e=>{this._period=e,this._scheduleFetch()}),this._unfilter=ae(this._config?.collection_key,()=>this._scheduleFetch())}_scheduleFetch(){this._fetchPending||(this._fetchPending=!0,queueMicrotask(()=>{this._fetchPending=!1,this._fetch()}))}_refetchIfDevicesChanged(){let e=this._devices().map(r=>r.key).join(",");e!==this._deviceKeys&&(this._deviceKeys=e,this._period&&this._scheduleFetch())}_devices(){let e=y(this._hass),r=this._config?.devices,o=r?e.filter(a=>r.includes(a.key)):e,s=this._filter();return o.filter(a=>it(a,s))}_filter(){return Y(this._config?.collection_key)}_isFiltered(){return!!this._config?.devices||this._filter().kind!=="all"}async _fetch(){if(!this._hass||!this._period)return;let e=this._devices(),r=++this._request;if(await T(this._hass),e.length===0){this._state="empty",this._render();return}let o=this._isFiltered()?void 0:tt(this._hass);try{let s=rt(this._hass),[a,n]=await Promise.all([Se(this._hass,e,this._period,o,s),this._period.compare?Se(this._hass,e,this._period.compare,o):void 0]);if(r!==this._request)return;this._result=Et(a,n),this._state="ready"}catch(s){if(r!==this._request)return;this._state="error",console.error(`${this.localName}: could not load statistics`,s)}this._render()}_render(){let e=ie(this._hass);this.shadowRoot.innerHTML=`
      <style>${so}${this.constructor.cardStyle}${no}</style>
      <ha-card>
        <div class="body" data-state="${this._state}">${this._content(e)}</div>
      </ha-card>
    `;let r=this._config?.title??this._labels[this._titleKey()];r&&this._writeHeader(r,e),this._afterRender()}_writeHeader(e,r){let o=this.shadowRoot.querySelector("ha-card"),s=this._headerChip(r);if(s===void 0){o.setAttribute("header",e);return}o.insertAdjacentHTML("afterbegin",`<div class="card-header" style="display: flex; justify-content: space-between;
         align-items: center; gap: var(--hea-space-s); padding-bottom: 0;">
        <span class="title">${g(e)}</span>
        <span class="chip">${g(s)}</span>
      </div>`)}_headerChip(){}_afterRender(){}_content(e){return this._state==="empty"?`<p class="message">${this._labels.no_devices}</p>`:this._state==="error"?`<p class="message">${this._labels.statistics_failed}</p>`:`${this._body(e)}${this._caption(e)}`}_caption(e){let r=this._period?.fallback?`<div class="hint">${this._labels.no_picker}</div>`:"";return`<div class="period">${this._periodLabel(e)}</div>${r}`}_periodLabel(e){let r=Z(this._period,e),o=this._period?.compare;return o?v(this._labels.compared_period,{period:r,compared:Z(o,e)}):r}},f=(t,e,{name:r,description:o})=>{customElements.get(t)||customElements.define(t,e),globalThis.customCards=globalThis.customCards??[],globalThis.customCards.some(s=>s.type===t)||globalThis.customCards.push({type:t,name:r,description:o})};var ao={title:"editor_title",collection_key:"editor_collection_key",devices:"editor_devices",sort_by:"editor_sort_by",layout:"editor_layout",metric:"editor_metric",group_by_floor:"editor_group_by_floor",group_by_area:"editor_group_by_area",range:"editor_range"},h=class extends HTMLElement{constructor(){super(),this.attachShadow({mode:"open"})}setConfig(e){this._config=e,this._render()}set hass(e){this._hass=e,this._render(),T(e).then(()=>this._render())}_extraSchema(){return[]}_render(){if(!this._config)return;let e=this.shadowRoot.querySelector("ha-form");e||(e=document.createElement("ha-form"),e.computeLabel=r=>b(this._hass)[ao[r.name]]??r.name,e.addEventListener("value-changed",r=>this._report(r.detail.value)),this.shadowRoot.append(e)),e.hass=this._hass,e.data=this._config,e.schema=this._schema()}_schema(){return[{name:"title",selector:{text:{}}},{name:"collection_key",selector:{text:{}}},{name:"devices",selector:{select:{multiple:!0,mode:"list",options:y(this._hass).map(e=>({value:e.key,label:e.name}))}}},...this._extraSchema()]}_report(e){this.dispatchEvent(new CustomEvent("config-changed",{detail:{config:io({...this._config,...e})},bubbles:!0,composed:!0}))}},io=t=>Object.fromEntries(Object.entries(t).filter(([,e])=>e!==""&&e!==void 0&&e!==null&&!(Array.isArray(e)&&e.length===0))),_=(t,e)=>{customElements.get(t)||customElements.define(t,e)};var w=class extends F{static chartTag="ha-chart-base";static bearingCard={type:"statistics-graph",entities:[]};static emptyKey="no_cost_in_period";static chartHeight="clamp(320px, 40vw, 480px)";static cardStyle=`
    ha-chart-base { display: block; --chart-max-height: none; }
  `;constructor(){super(),this._chartReady=!!customElements.get(this.constructor.chartTag)}getCardSize(){return 6}connectedCallback(){super.connectedCallback(),this._chartReady||this._loadChartComponent()}async _loadChartComponent(){let{chartTag:e,bearingCard:r}=this.constructor;customElements.whenDefined(e).then(()=>{this._chartReady=!0,this._render()});try{await(await globalThis.loadCardHelpers?.())?.createCardElement(r)}catch(o){console.warn(`${e}: could not be loaded`,o)}}_isEmpty(){return(this._result?.series??[]).length===0}_body(){return this._chartReady?this._isEmpty()?`<p class="message">${this._labels[this._emptyKey()]}</p>`:this._chartMarkup():`<p class="message">${this._labels.chart_not_loaded}</p>`}_emptyKey(){return this.constructor.emptyKey}_chartMarkup(){return'<ha-chart-base chart-type="bar"></ha-chart-base>'}_afterRender(){let e=this.shadowRoot.querySelector(this.constructor.chartTag);e&&(e.hass=this._hass,this._draw(e))}_chartHeight(){return this.constructor.chartHeight}_draw(e){e.height=this._chartHeight(),e.data=this._series(),e.options=this._options(this._chartLocale())}_chartLocale(){return ie(this._hass)}_colour({variable:e,fallback:r}){return getComputedStyle(this).getPropertyValue(e).trim()||r}};var co=/^#([\da-f]{3}|[\da-f]{6})$/i,lo=/^rgba?\(([^)]+)\)$/i,Te=t=>{let e=co.exec(String(t).trim());if(e){let s=e[1];return(s.length===3?[...s].map(n=>n+n):[0,2,4].map(n=>s.slice(n,n+2))).map(n=>Number.parseInt(n,16))}let r=lo.exec(String(t).trim());if(!r)return;let o=r[1].split(/[\s,/]+/).filter(Boolean).slice(0,3).map(Number);return o.length===3&&o.every(Number.isFinite)?o:void 0},A=(t,e)=>{let r=Te(String(t).trim());return r?`rgba(${r.join(", ")}, ${e})`:t},uo=([t,e,r])=>(.2126*t+.7152*e+.0722*r)/255,ce=t=>{let e=Te(ho(t));return e?uo(e)>.5:!1},ho=t=>{let e=[t,t?.ownerDocument?.documentElement].filter(Boolean);for(let r of e){let o=getComputedStyle(r),s=o.getPropertyValue("--primary-text-color").trim()||o.color;if(Te(s))return s}return""};var Ot=Object.freeze({variable:"--primary-color",fallback:"#03a9f4"}),Ct=Object.freeze({variable:"--success-color",fallback:"#4caf50"}),mo=Object.freeze({paid:"paid",would_have_paid:"would-have-paid",saved:"saved"}),le=`
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
`,de=t=>{let e=typeof t=="string"?mo[t]:void 0;return e?`<span class="swatch ${e}" aria-hidden="true"></span>`:""};var R=(t,e,r,{bold:o=!1}={})=>{let s=document.createElement("div");s.style.display="flex",s.style.justifyContent="space-between",s.style.gap="16px",o&&(s.style.fontWeight="bold");let a=document.createElement("span");a.textContent=t;let n=document.createElement("span");return n.textContent=e,n.style.fontVariantNumeric="tabular-nums",r&&(n.style.color=r),s.append(a,n),s},po=t=>{let e=document.createElement("span");return e.style.display="inline-block",e.style.width="10px",e.style.height="10px",e.style.borderRadius="10px",e.style.marginInlineEnd="4px",e.style.verticalAlign="middle",e.style.backgroundColor=t,e},Ft=(t,e,r,o)=>{let s=R(e,r,o);return s.firstChild.prepend(po(t)),s},ue=t=>{let e=document.createElement("div");return e.textContent=t,e.style.fontWeight="bold",e.style.textAlign="center",e.style.marginBottom="4px",e},Rt=t=>{let e=document.createElement("div");return e.textContent=t,e.style.marginTop="4px",e.style.maxWidth="260px",e.style.whiteSpace="normal",e.style.opacity="0.7",e};var Dt="hea-cost-over-time-card",Lt=`${Dt}-editor`,fo={hour:3600*1e3,day:1440*60*1e3},_o=50,go=.5,yo=(t,e)=>{if(!t.length||!e)return 0;let r=fo[C(e)]??0,o=t.length>=2?t[1].start.getTime()-t[0].start.getTime():void 0;return(o?Math.min(o,r):r)/2},$={paid:{id:"paid",name:"paid",...Ot},saved:{id:"saved",name:"saved",...Ct}},Mt={variable:"--error-color",fallback:"#db4437"},bo={gain:{variable:"--success-color",fallback:"#4caf50"},loss:Mt},Oe=t=>t.value?.[1]??0,vo=t=>t.value?.[2],xo=.45,he={id:"before",name:"compared_series",variable:"--secondary-text-color",fallback:"#727272"},Ce=class extends w{static titleKey="title_cost_over_time";static getConfigElement(){return document.createElement(Lt)}_series(){let e=kt(this._result?.series??[],this._result?.period),r=this._colour(Mt),o=this._labels,s=this._result?.seriesBefore,a=yo(e,this._result?.period);return[...oe([{...It($.paid,this._colour($.paid),o),data:e.map(n=>$t(n,Nt(n,n.actualCost,a)))},{...It($.saved,this._colour($.saved),o),data:e.map(n=>{let i=Nt(n,n.costSavings,a),c=n.costSavings<0?Gt(r):void 0;return $t(n,i,c)})}]),...s?.length?[{id:he.id,name:o[he.name],type:"line",symbol:"none",lineStyle:{type:"dashed",width:2},itemStyle:{color:this._colour(he)},data:s.map(n=>[n.start.getTime()+a,n.costAtGridPrice])}]:[]]}_caption(e){return`${super._caption(e)}${this._stillAccruingNote()}`+this._accrualNote()}_stillAccruingNote(){return(this._result?.series??[]).some(e=>e.accruing)?`<div class="hint">${this._labels.still_accruing}</div>`:""}_accrualNote(){return this._devices().length!==1||!this._period||C(this._period)!=="hour"?"":`<div class="hint">${this._labels.hourly_shape_estimate}</div>`}_tooltipFor(e,r){let o=(Array.isArray(e)?e:[e]).filter(c=>c.componentSubType==="bar"),s=o.filter(c=>Oe(c)!==0);if(!s.length)return;let a=this._bucketAt(o.map(vo).find(c=>c!==void 0)),n=document.createElement("div");n.append(ue(this._spanOf(a,r)));for(let c of s)n.append(this._tooltipRowFor(c,r));let i=o.reduce((c,l)=>c+Oe(l),0);return s.length>1&&n.append(R(this._labels.would_have_paid,u(i,r),void 0,{bold:!0})),a?.accruing&&n.append(Rt(this._labels.still_accruing)),n}_tooltipRowFor(e,r){let o=Oe(e),a=e.seriesId===$.saved.id&&o<0?this._labels.lost:e.seriesName,n=e.seriesId===$.saved.id?S(o):"";return Ft(e.color,a,u(o,r),n?this._colour(bo[n]):void 0)}_bucketAt(e){if(e!==void 0)return(this._result?.series??[]).find(r=>r.start.getTime()===e)}_spanOf(e,r){return!e||!this._period?"":lt(e.start,C(this._period),r)}_headerChip(e){let r=this._result?.totals?.actualCost;return Number.isFinite(r)&&!this._isEmpty()?u(r,e):""}_axisBounds(){if(!this._period)return{};let{start:e,end:r}=this._period,o=new Date(r.getTime()-1);return C(this._period)==="hour"?o.setMinutes(30,0,0):(o.getHours()===0&&o.setHours(o.getHours()-1),o.setHours(0,0,0,0)),{min:e.getTime(),max:o.getTime()}}_options(e){let r=this._labels;return{xAxis:{type:"time",...this._axisBounds()},grid:{top:15,bottom:0,left:1,right:1,containLabel:!0},yAxis:{type:"value",name:q(e),nameGap:2,nameTextStyle:{align:"left"},boundaryGap:[0,0],splitNumber:5,splitLine:{show:!0},axisLabel:{formatter:o=>V(o,e),hideOverlap:!0}},tooltip:{trigger:"axis",axisPointer:{type:"shadow"},formatter:o=>this._tooltipFor(o,e)},legend:{show:!0,type:"custom",data:[$.paid,$.saved,...this._result?.seriesBefore?.length?[he]:[]].map(o=>({id:o.id,name:r[o.name],itemStyle:{color:this._colour(o)}}))}}}},$t=(t,e,r=void 0)=>t.accruing?{value:e,itemStyle:{...r,opacity:xo}}:r?{value:e,itemStyle:r}:e,Nt=(t,e,r)=>[t.start.getTime()+r,e,t.start.getTime()],It=({id:t,name:e},r,o)=>({id:t,name:o[e],type:"bar",stack:"cost",barMaxWidth:_o,itemStyle:Gt(r)}),Gt=t=>({color:A(t,go),borderColor:t,borderWidth:1}),Fe=class extends h{},wo=()=>{_(Lt,Fe),f(Dt,Ce,{name:"Home Energy Advisor: Cost over time",description:"What the period cost, stacked against what it would have cost at grid price."})};wo();var Ie="hea",jt="Home Energy Advisor",Eo="mdi:home-lightning-bolt",Ht=`ll-strategy-dashboard-${Ie}`,Pt=`ll-strategy-view-${Ie}`,Q=4,ko=[{type:"custom:hea-totals-card"},{type:"custom:hea-devices-card",sort_by:"actual_cost"}],Ao=[{type:"custom:hea-cost-over-time-card"},{type:"custom:hea-sources-card",sort_by:"energy_used"}],So=[{type:"custom:hea-device-costs-card"},{type:"custom:hea-distribution-card"},{type:"custom:hea-self-sufficiency-card"}],To=t=>({...t,grid_options:{columns:"full",rows:"auto"}}),Re=(t,e)=>({type:"grid",column_span:e,cards:t.map(To)}),Oo=()=>({card:{type:"horizontal-stack",cards:[{type:"energy-date-selection",vertical_opening_direction:"up"},{type:"custom:hea-filter-card"}]},max_width:1600}),Co=t=>({type:"sections",max_columns:Q,sections:[{type:"grid",cards:[{type:"markdown",content:b(t).no_devices}]}]}),Fo=t=>y(t).length===0?Co(t):{type:"sections",max_columns:Q,sections:[Re(ko,Q),Re(Ao,Q/2),Re(So,Q/2)],footer:Oo()},Ut=async t=>(await T(t),Fo(t)),$e=class extends HTMLElement{static async generate(e,r){return{views:[await Ut(r)]}}static noEditor=!0;static getCreateSuggestions(){return{title:jt,icon:Eo}}},Ne=class extends HTMLElement{static async generate(e,r){return Ut(r)}},Ro=t=>{globalThis.customStrategies=globalThis.customStrategies??[],globalThis.customStrategies.some(e=>e.type===t.type)||globalThis.customStrategies.push(t)},$o=()=>{customElements.get(Ht)||customElements.define(Ht,$e),customElements.get(Pt)||customElements.define(Pt,Ne),Ro({type:Ie,strategyType:"dashboard",name:jt,description:"What each device cost to run, and what solar and the battery saved."})};$o();var Bt=Object.keys(U),No=Object.keys(O),zt=t=>{let e=new Map;for(let r of t){if(!r.upstream)continue;let o=e.get(r.upstream);o?o.push(r):e.set(r.upstream,[r])}return e},me=(t,e)=>({...t,key:`${t.key}${Io}`,name:`${t.name} ${e.device_untracked}`,upstream:t.key,untracked:!1,residualOf:t.key}),Io="__untracked",Do=t=>{let e=Object.fromEntries(Bt.map(r=>[r,0]));for(let r of t)for(let o of Bt)e[o]+=r[o]??0;for(let r of No)e[r]=t.every(o=>typeof o[r]=="number")?t.reduce((o,s)=>o+s[r],0):void 0;return e.costSavings=e.costAtGridPrice-e.actualCost,e},pe=(t,e)=>{let r=zt(t);return r.size===0?t:t.flatMap(o=>r.has(o.key)?[me(o,e)]:[o])},Wt=(t,e,r=o=>o)=>{let o=zt(t);if(o.size===0)return r(t).map(a=>({device:a,depth:0}));let s=(a,n)=>{if(!o.has(a.key))return[{device:a,depth:n}];let c=r([...o.get(a.key),me(a,e)]).flatMap(d=>s(d,n+1)),l=c.filter(d=>!d.device.subtotal).map(d=>d.device);return[{device:{...a,...Do(l),subtotal:!0},depth:n},...c]};return r(t.filter(a=>!a.upstream)).flatMap(a=>s(a,0))};var E=Object.freeze(["#0072b2","#e69f00","#009e73","#cc79a7","#56b4e9","#d55e00","#8c6bb1","#3d9970"]),Lo=Object.freeze(["#4b46b3","#8d9b1f","#00a2ab","#b07ad2","#7fa0ee","#a8761b","#b26596","#5b8f3f"]),De=Object.freeze([E,Lo]),Tn=E.length*De.length,B=Object.freeze({variable:"--secondary-text-color",fallback:"#8a8a8a"}),z=t=>{let e=(t??[]).filter(r=>!r.untracked).map(r=>r.key).sort(Mo);return new Map(e.map((r,o)=>{let s=Math.floor(o/E.length)%De.length;return[r,De[s][o%E.length]]}))},Mo=(t,e)=>t===e?0:t<e?-1:1;var fe=(t,e,r)=>{let o=t<0?e.lost_share:e.saved_share;return v(o,{percent:j(Math.abs(t),r)})},Go=({costSavings:t,costAtGridPrice:e})=>{if(!(!Number.isFinite(t)||!Number.isFinite(e))&&!(e<=0))return t/e},J=[{at:0,hue:3,light:48,dark:62},{at:.5,hue:35,light:46,dark:68},{at:1,hue:142,light:31,dark:76}],Kt={light:85,dark:70},Ho=.7,Yt=(t,e,r)=>t+(e-t)*r,Po=.6,jo=(t,e)=>{let r=J.findIndex(i=>t<=i.at);if(r<=0)return{hue:J[0].hue,lightness:J[0][e]};let o=J[r-1],s=J[r],a=(t-o.at)/(s.at-o.at),n=r===1?a:a**Po;return{hue:Yt(o.hue,s.hue,n),lightness:Yt(o[e],s[e],a)}},Vt=.05,I=t=>Math.round(t*10)/10,_e=(t,{dark:e=!1}={})=>{let r=e?"dark":"light",o=a=>Math.max(0,a?.costAtGridPrice??0),s=Math.max(0,...(t??[]).map(o));return a=>{let n=Go(a??{});if(n===void 0||s<=0)return;let i=Math.min(1,o(a)/s),c=i*(1+Vt)/(i+Vt),l=Math.min(1,Math.max(0,n)),{hue:d,lightness:m}=jo(l,r),x=Kt[r]*c**Ho;return{rate:n,text:`hsl(${I(d)}, ${I(x)}%, ${I(m)}%)`,edge:`hsla(${I(d)}, ${I(Kt[r])}%, ${I(m)}%, ${I(c)})`}}};var tr="hea-device-costs-card",rr=`${tr}-editor`,qt={variable:"--error-color",fallback:"#db4437"},Uo={variable:"--secondary-text-color",fallback:"#727272"},Bo="earlier-period",zo=["auto","vertical","horizontal"],Wo="paid",Ko="saved",Zt="before",Yo=30,Vo=46,qo=64,Zo=240,Xo=24,Qo=12,Jo=2,es=10,ts=300,rs=120,os="40vw",ss={left:8,right:16,top:8,bottom:28,containLabel:!0},Xt=1.5,Qt=.8,Jt=.45,er=.22,ns=/:(?:paid|saved|before)$/,as={gain:{variable:"--success-color",fallback:"#4caf50"},loss:{variable:"--error-color",fallback:"#db4437"}},is=(t,e,r,o,s,a)=>{let n=S(t.costSavings),i=document.createElement("div");i.append(ue(e),R(o.paid,u(t.actualCost,r)),R(t.costSavings<0?o.lost:o.saved,u(t.costSavings,r),n?s(n):void 0),R(o.would_have_paid,u(t.costAtGridPrice,r)));let c=cs(a,r,o);c&&i.append(c);let l=ls(t,r,o,s);l&&i.append(l);let d=ds(t,r,o);return d&&i.append(d),i},cs=(t,e,r)=>{if(!t)return;let o=document.createElement("div");return o.style.marginTop="4px",o.style.color=t.text,o.textContent=fe(t.rate,r,e),o},ls=(t,e,r,o)=>{let s=t.before?.actualCost;if(!Number.isFinite(s)||!Number.isFinite(t.actualCost))return;let a=t.actualCost-s,n=H("actualCost",a);return R(r.change,v(r.compared,{change:G(a,e),before:u(s,e)}),n?o(n):void 0)},ds=({costFloor:t,costCeiling:e},r,o)=>{if(![t,e].every(a=>Number.isFinite(a)))return;let s=document.createElement("div");return s.style.marginTop="4px",s.style.opacity="0.75",s.textContent=v(o.range_device,{range:P([t,e],r)}),s},Le=class extends w{static titleKey="title_device_costs";static narrowQuery=N;static getConfigElement(){return document.createElement(rr)}_isEmpty(){return this._ranked().every(e=>!e.costAtGridPrice&&!e.actualCost)}_ranked(){return pe(this._result?.devices??[],this._labels).sort((e,r)=>r.actualCost-e.actualCost||e.name.localeCompare(r.name))}_colourFor(e){if(e.untracked)return this._colour(B);let r=e.residualOf??e.key;return this._colours().get(r)??E[0]}_colours(){return z(y(this._hass))}_verdicts(){return _e(this._ranked(),{dark:ce(this)})}_sideways(){let e=this._config?.layout;return e==="horizontal"?!0:e==="vertical"?!1:this._isNarrow()}_comparing(){return this._ranked().some(e=>e.before)}_series(){return oe(this._sideways()?this._sidewaysSeries():this._standingSeries())}_sidewaysSeries(){let e=this._ranked(),r=this._colour(qt),o=this._labels,s=a=>this._colourFor(a);return[{id:Wo,name:o.paid,type:"bar",stack:"cost",data:e.map(a=>({value:a.actualCost,itemStyle:{color:A(s(a),Qt)}}))},{id:Ko,name:o.saved,type:"bar",stack:"cost",data:e.map(a=>{let n=a.costSavings<0?r:s(a);return{value:a.costSavings,itemStyle:{color:A(n,er),borderColor:n,borderWidth:Xt}}})},...this._comparing()?[{id:Zt,name:o.compared_series,type:"bar",stack:"earlier",data:e.map(a=>({value:a.before?a.before.actualCost:null,itemStyle:{color:A(s(a),Jt)}}))}]:[]]}_standingSeries(){let e=this._colour(qt);return this._ranked().flatMap(r=>{let o=this._colourFor(r),s=r.costSavings<0?e:o,a=r.name;return[{id:`${r.key}:paid`,name:a,type:"bar",stack:r.key,itemStyle:{color:A(o,Qt)},data:[r.actualCost]},{id:`${r.key}:saved`,name:a,type:"bar",stack:r.key,itemStyle:{color:A(s,er),borderColor:s,borderWidth:Xt},data:[r.costSavings]},...r.before?[{id:`${r.key}:before`,name:a,type:"bar",stack:`${r.key}:before`,itemStyle:{color:A(o,Jt)},data:[r.before.actualCost]}]:[]]})}_tooltipFor({seriesId:e,dataIndex:r},o){let s=this._ranked(),a=this._sideways()?s[r]:s.find(n=>n.key===String(e??"").replace(ns,""));return a?is(a,a.name,o,this._labels,n=>this._colour(as[n]),this._verdicts()(a)):void 0}_earlierKey(){if(!this._comparing())return[];let e=this._labels.compared_series,r={color:this._colour(Uo)};return this._sideways()?[{id:Zt,name:e,itemStyle:r}]:[{id:Bo,secondaryIds:this._ranked().filter(o=>o.before).map(o=>`${o.key}:before`),name:e,itemStyle:r}]}_chartHeight(){if(this._sideways()){let r=this._ranked().length,o=this._comparing()?Vo:Yo;return`${Math.max(Zo,qo+r*o)}px`}let e=ts+this._legendHeight();return`clamp(${e}px, ${os}, ${e+rs}px)`}_legendHeight(){let e=Math.min(this._ranked().length,es)+this._earlierKey().length;return Math.ceil(e/Jo)*Xo+Qo}_options(e){return this._sideways()?this._sidewaysOptions(e):this._standingOptions(e)}_sidewaysOptions(e){let r=this._earlierKey();return{xAxis:{type:"value",name:q(e),axisLabel:{formatter:o=>V(o,e),hideOverlap:!0}},yAxis:{type:"category",data:this._ranked().map(o=>o.name),inverse:!0},grid:ss,tooltip:{trigger:"item",formatter:o=>this._tooltipFor(o,e)},...r.length?{legend:{show:!0,type:"custom",data:r}}:{}}}_standingOptions(e){return{xAxis:{type:"category",data:[Z(this._period,e)]},yAxis:{type:"value",name:q(e),nameGap:2,nameTextStyle:{align:"left"},axisLabel:{formatter:r=>V(r,e),hideOverlap:!0}},tooltip:{trigger:"item",formatter:r=>this._tooltipFor(r,e)},legend:{show:!0,type:"custom",data:[...this._ranked().map(r=>({id:`${r.key}:paid`,secondaryIds:[`${r.key}:saved`,...r.before?[`${r.key}:before`]:[]],name:r.name,itemStyle:{color:this._colourFor(r)}})),...this._earlierKey()]}}}},Me=class extends h{_extraSchema(){return[{name:"layout",selector:{select:{mode:"dropdown",options:zo}}}]}},us=()=>{_(rr,Me),f(tr,Le,{name:"Home Energy Advisor: Device costs (chart)",description:"What each device cost over the selected period, dearest first."})};us();var hs=`${le}
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
`,ms=(t,e,r)=>(t==="costSavings"?S(r):H(e,r))??"",Ge=({classes:t=[],styles:e=[]})=>{let r=t.filter(Boolean),o=e.filter(Boolean);return(r.length?` class="${r.join(" ")}"`:"")+(o.length?` style="${o.join("; ")}"`:"")},or=t=>t?`box-shadow: inset ${ps} 0 0 ${t.edge}`:"",ps="4px",D=class extends F{static columns=[];static sorts={};static defaultSort="";static cardStyle=hs;setConfig(e){let{sorts:r}=this.constructor;if(e.sort_by!==void 0&&!(e.sort_by in r))throw new Error(`\`sort_by\` must be one of: ${Object.keys(r).join(", ")}`);super.setConfig(e)}getCardSize(){return 3+Math.ceil((this._result?.devices.length??3)/2)}_columns(){return this.constructor.columns}_body(e){let r=this._columns(),o=this._verdictScale();return`
      <div class="scroll">
        <table>
          <thead><tr>${r.map(s=>this._heading(s,e)).join("")}</tr></thead>
          <tbody>${this._ranked().map(({device:s,depth:a})=>this._row(s,e,o,a)).join("")}</tbody>
          <tfoot>${this._total(e,o)}</tfoot>
        </table>
      </div>`}_verdictScale(){if(this._columns().some(e=>e.carriesVerdict))return _e(this._result?.devices??[],{dark:ce(this)})}_heading({label:e},r){let o=this._labels;if(typeof e!="function")return`<th>${de(e)}${o[e]}</th>`;let{text:s,unit:a}=e(r,o);return`<th>${s} <span class="unit">${g(a)}</span></th>`}_rank(e){let{sorts:r,defaultSort:o}=this.constructor,{field:s}=r[this._config?.sort_by??o];return[...e].sort((a,n)=>n[s]-a[s]||a.name.localeCompare(n.name))}_ranked(){return Wt(this._result?.devices??[],this._labels,e=>this._rank(e))}_row(e,r,o,s){return`<tr${e.subtotal?' class="subtotal"':""}>${this._columns().map(n=>this._cell(n,e,r,o?.(e),s)).join("")}</tr>`}_cell(e,r,o,s,a){let{field:n,derive:i,format:c,reveal:l}=e;if(!c)return`<th scope="row"${Ge({classes:[a?"inside":""],styles:[a?`--depth: ${a}`:"",or(s)]})}>${g(r.name)}</th>`;let d=i?i(r):r[n],m=this._revealed(c(d,o),l?.(r,o,this._labels));return`<td${this._figureAttributes(e,d,s,o)}>${m}</td>`}_figureAttributes({field:e,tone:r,muted:o,carriesVerdict:s},a,n,i){let c=s?this._verdictOn(n,i):null;return Ge({classes:[ms(e,r,a),o?"muted":""],styles:[c?.style]})+(c?` title="${g(c.title)}"`:"")}_revealed(e,r){return r?`<span class="reveal" tabindex="0" aria-label="${g(r.label)}">${e}<span class="revealed" aria-hidden="true">${g(r.text)}</span></span>`:e}_total(e,r){let o=this._sumOfShown(),s=r?.(o);return`<tr>${this._columns().map(n=>{let{field:i,derive:c,format:l}=n;if(!l)return`<th scope="row"${Ge({styles:[or(s)]})}>${this._labels.total}</th>`;let d=c?c(o):o[i];return`<td${this._figureAttributes(n,d,s,e)}>${l(d,e)}</td>`}).join("")}</tr>`}_verdictOn(e,r){return e?{style:`color: ${e.text}`,title:fe(e.rate,this._labels,r)}:null}_sumOfShown(){let e=[...new Set(this._columns().flatMap(({field:n,fields:i,derive:c,format:l})=>l?c?i??[]:n?[n]:[]:[]))],r=pe(this._result?.devices??[],this._labels),o=Object.fromEntries(this._columns().flatMap(({fields:n,field:i,readField:c})=>c?(n??[i]).map(l=>[l,c]):[])),s=n=>r.reduce((i,c)=>{for(let l of e){let d=n(c);i[l]+=o[l]?o[l](d,l):d[l]}return i},Object.fromEntries(e.map(i=>[i,0]))),a=s(n=>n);return r.length>0&&r.every(n=>n.before)&&(a.before=s(n=>n.before)),a}},ge=(t,e)=>[{name:"sort_by",selector:{select:{mode:"dropdown",options:Object.entries(t).map(([r,{label:o}])=>({value:r,label:e[o]}))}}}];var nr="hea-devices-card",ar=`${nr}-editor`,fs=({actualCost:t,energyUsed:e})=>e>0?t/e:void 0,ir=t=>Object.values(O).every(e=>e in(t.statistics??{})),ee={fields:["costFloor","costCeiling"],derive:({costFloor:t,costCeiling:e})=>[t,e],label:"range_column",format:P,readField:(t,e)=>Number.isFinite(t[e])?t[e]:t.actualCost},cr={fields:["actualCost"],derive:({actualCost:t,before:e})=>e&&Number.isFinite(t)&&Number.isFinite(e.actualCost)?t-e.actualCost:void 0,label:"change",format:G,tone:"actualCost"},ye={field:"actualCost",label:"paid",format:u,carriesVerdict:!0,reveal:(t,e)=>{if(!ir(t)||!ee.fields.every(o=>Number.isFinite(t[o])))return null;let r=P(ee.derive(t),e);return{text:r,label:`${u(t.actualCost,e)} (${r})`}}},lr={field:"forgoneExport",label:"forgone_column",format:u,muted:!0},sr=[{field:"name",label:"device"},{field:"energyUsed",label:"energy",format:k},ye,cr,ee,{field:"costAtGridPrice",label:"would_have_paid",format:u,muted:!0},{field:"costSavings",label:"saved",format:u},lr,{derive:fs,label:(t,e)=>({text:e.rate,unit:ht(t)}),format:mt}],dr={actual_cost:{field:"actualCost",label:"paid"},cost_at_grid_price:{field:"costAtGridPrice",label:"would_have_paid"},cost_savings:{field:"costSavings",label:"saved"},energy_used:{field:"energyUsed",label:"energy_used"}},He=class extends D{static titleKey="title_devices";static columns=sr;static sorts=dr;static defaultSort="actual_cost";static narrowQuery=N;static cardStyle=`${D.cardStyle}
    .disclosure {
      margin-top: var(--hea-space-m);
      color: var(--secondary-text-color);
      font-size: 0.8em;
    }
  `;static getConfigElement(){return document.createElement(ar)}_columns(){let e=this._rangeAsColumn(),r=new Set;return e||r.add(ee),this._showsForgone()||r.add(lr),this._hasComparison()||r.add(cr),sr.filter(o=>!r.has(o)).map(o=>o!==ye?o:e?{...ye,reveal:void 0}:ye)}_rangeAsColumn(){let e=this._config?.range;return(e==="column"||e!=="rollover"&&!this._isNarrow())&&this._hasEveryBound()}_showsForgone(){return this._hasForgone()&&!this._isNarrow()}_hasComparison(){return(this._result?.devices??[]).some(e=>e.before)}_hasForgone(){return(this._result?.devices??[]).some(e=>(e.forgoneExport??0)>0)}_hasEveryBound(){let e=(this._result?.devices??[]).filter(ir);return e.length>0&&e.every(r=>ee.fields.every(o=>Number.isFinite(r[o])))}_body(e){return`${super._body(e)}${this._disclosure(e)}`}_disclosure(e){let r=[this._rangeDisclosure(e),this._forgoneNote()].filter(Boolean);return r.length?`<div class="disclosure">${r.join(" ")}</div>`:""}_forgoneNote(){return this._hasForgone()?this._showsForgone()?this._labels.forgone_note:this._labels.forgone_hidden_note:""}_rangeDisclosure(e){if(this._hasEveryBound())return this._rangeNote();let r=this._result?.wholeHome;if(!r)return"";let o=P([r.costFloor,r.costCeiling],e);return v(this._labels.range_whole_home,{range:o})}_rangeNote(){return this._rangeAsColumn()?this._labels.range_note:this._labels.range_note_rollover}},Pe=class extends h{_extraSchema(){let e=b(this._hass);return[...ge(dr,e),{name:"range",selector:{select:{mode:"dropdown",options:[{value:"auto",label:e.editor_range_auto},{value:"rollover",label:e.editor_range_rollover},{value:"column",label:e.editor_range_column}]}}}]}},_s=()=>{_(ar,Pe),f(nr,He,{name:"Home Energy Advisor: Devices",description:"Every tracked device over the selected period, ordered by what it cost."})};_s();var te="household",W=Object.freeze({source:0,household:1,floor:2,area:3,device:4}),ur=Object.freeze({cost:{field:"actualCost",sources:null},energy:{field:"energyUsed",sources:[{id:"grid",field:"energyFromGrid",variable:"--energy-grid-consumption-color",fallback:"#488fc2"},{id:"generation",field:"energyFromGeneration",variable:"--energy-solar-color",fallback:"#ff9800"},{id:"battery",field:"energyFromBattery",variable:"--energy-battery-out-color",fallback:"#4db6ac"}]}}),gs=t=>{let e=z(t);return r=>r.untracked?B.fallback:e.get(r.key)??E[0]},ys=({fallback:t})=>t,fr=(t,e,{metric:r="cost",colour:o=ys,deviceColour:s=gs(t),groupByFloor:a=!0,groupByArea:n=!0}={})=>{let{field:i,sources:c}=ur[r]??ur.cost,l=bs(t,i).filter(p=>p.value>0);if(l.length===0)return{nodes:[],links:[]};let d=l.reduce((p,Cr)=>p+Cr.value,0),m=xs(l,{groupByFloor:a,groupByArea:n}),x=ws(l,e,s),K=Es(c,t.filter(p=>p[i]>0),e,o);return{nodes:[...K,{id:te,label:e.household,value:d,index:W.household},...m.nodes,...x.nodes],links:[...K.map(p=>({source:p.id,target:te,value:p.value})),...m.links,...x.links]}},bs=(t,e)=>{let r=new Map(t.map(n=>[n.key,n])),o=new Map,s=[];for(let n of t){let i=vs(n,r);i?o.has(i.key)?o.get(i.key).push(n):o.set(i.key,[n]):s.push(n)}let a=n=>{let i=Math.max(n[e]??0,0),c=(o.get(n.key)??[]).map(a).filter(l=>l.value>0);return{device:n,own:i,inside:c,value:c.reduce((l,d)=>l+d.value,i)}};return s.map(a)},vs=(t,e)=>{let r=e.get(t.upstream);if(!r)return null;let o=new Set;for(let s=r;s;s=e.get(s.upstream)){if(s.key===t.key)return null;if(o.has(s.key))break;o.add(s.key)}return r},xs=(t,{groupByFloor:e,groupByArea:r})=>{let o=new Map,s=new Map,a=[];return t.forEach(({device:n,value:i})=>{let c=e&&n.floorId?hr(o,n.floorId,n.floorName):null,l=r&&n.areaId?hr(s,n.areaId,n.areaName):null;c&&(c.value+=i),l&&(l.value+=i,l.floorId??=c?.id??null),a.push({source:ks(l,c),target:L(n),value:i})}),{nodes:[...pr(o,"floor_",W.floor),...pr(s,"area_",W.area)],links:[...As(o,s),...a]}},ws=(t,e,r)=>{let o=W.device+_r(t),s=[],a=[],n=(i,c)=>{let{device:l,own:d,inside:m,value:x}=i,K=m.length>0;if(s.push({id:L(l),label:l.name,value:x,index:K?W.device+c:o,color:r(l),...mr(l)}),!!K&&(m.forEach(p=>{a.push({source:L(l),target:L(p.device),value:p.value}),n(p,c+1)}),d>0)){let p=me(l,e);s.push({id:L(p),label:p.name,value:d,index:o,color:r(l),...mr(l)}),a.push({source:L(l),target:L(p),value:d})}};return t.forEach(i=>n(i,0)),{nodes:s,links:a}},_r=t=>t.reduce((e,r)=>r.inside.length>0?Math.max(e,1+_r(r.inside)):e,0),L=t=>`device_${t.key}`,Es=(t,e,r,o)=>(t??[]).map(s=>({id:`source_${s.id}`,label:r[s.id],value:e.reduce((a,n)=>a+(n[s.field]??0),0),index:W.source,color:o(s)})).filter(s=>s.value>0),hr=(t,e,r)=>(t.has(e)||t.set(e,{id:e,name:r||e,value:0}),t.get(e)),ks=(t,e)=>t?`area_${t.id}`:e?`floor_${e.id}`:te,mr=t=>{let e=t.statistics?.actual_cost;return e?{entityId:e}:{}},pr=(t,e,r)=>[...t.values()].map(o=>({id:`${e}${o.id}`,label:o.name,value:o.value,index:r})),As=(t,e)=>[...[...t.values()].map(r=>({source:te,target:`floor_${r.id}`,value:r.value})),...[...e.values()].map(r=>({source:r.floorId?`floor_${r.floorId}`:te,target:`area_${r.id}`,value:r.value}))];var gr="hea-distribution-card",yr=`${gr}-editor`,re={cost:{titleKey:"title_distribution",emptyKey:"no_cost_in_period",format:u},energy:{titleKey:"title_distribution_energy",emptyKey:"no_energy_in_period",format:k}},Ss="400px",Ts=88,Os=240,Cs=["auto","horizontal","vertical"],je=Object.freeze({group_by_floor:!0,group_by_area:!0}),Ue=class extends w{static titleKey="title_distribution";static chartTag="ha-sankey-chart";static bearingCard={type:"energy-sankey"};static narrowQuery=N;static cardStyle=`
    ha-sankey-chart { display: block; min-height: 240px; }
  `;static getConfigElement(){return document.createElement(yr)}_isEmpty(){return this._layout().nodes.length===0}_verticalHeight({nodes:e}){let r=new Set(e.map(o=>o.index)).size;return`${Math.max(Os,r*Ts)}px`}_metric(){return re[this._config?.metric]?this._config.metric:"cost"}_titleKey(){return re[this._metric()].titleKey}_emptyKey(){return re[this._metric()].emptyKey}_layout(){let e=z(y(this._hass));return fr(this._result?.devices??[],this._labels,{metric:this._metric(),groupByFloor:this._config?.group_by_floor??je.group_by_floor,groupByArea:this._config?.group_by_area??je.group_by_area,colour:r=>this._colour(r),deviceColour:r=>r.untracked?this._colour(B):e.get(r.key)??E[0]})}_chartMarkup(){return"<ha-sankey-chart></ha-sankey-chart>"}_draw(e){e.data=this._layout(),e.vertical=this._isVertical(),e.style.height=this._isVertical()?this._verticalHeight(e.data):Ss;let r=this._chartLocale(),{format:o}=re[this._metric()];e.valueFormatter=s=>o(s,r),this.toggleAttribute("data-vertical",e.vertical)}_isVertical(){let e=this._config?.layout;return e==="vertical"?!0:e==="horizontal"?!1:this._isNarrow()}},Be=class extends h{_extraSchema(){return[{name:"metric",selector:{select:{mode:"dropdown",options:Object.keys(re)}}},{name:"layout",selector:{select:{mode:"dropdown",options:Cs}}},{name:"group_by_floor",selector:{boolean:{}}},{name:"group_by_area",selector:{boolean:{}}}]}setConfig(e){super.setConfig({...je,...e})}},Fs=()=>{_(yr,Be),f(gr,Ue,{name:"Home Energy Advisor: Cost distribution",description:"Where the period's cost went, by floor, room, circuit and device."})};Fs();var br="hea-filter-card",vr=`${br}-editor`,Rs=[{kind:"area",label:"filter_rooms",id:"areaId",name:"areaName"},{kind:"floor",label:"filter_floors",id:"floorId",name:"floorName"}],M=({kind:t,id:e})=>`${t}:${e??""}`,$s=t=>{let[e,r]=[t.slice(0,t.indexOf(":")),t.slice(t.indexOf(":")+1)];return{kind:e,id:r===""?null:r}},ze=class extends HTMLElement{constructor(){super(),this.attachShadow({mode:"open"})}setConfig(e){this._config=e,this._render()}set hass(e){this._hass=e,T(e).then(()=>this._renderIfChanged()),this._renderIfChanged()}getCardSize(){return 1}static getConfigElement(){return document.createElement(vr)}connectedCallback(){this._render(),this._unfilter??=ae(this._config?.collection_key,()=>this._renderIfChanged())}_signature(){return JSON.stringify([this._allDevices().map(e=>[e.key,e.name,e.areaId,e.areaName,e.floorId,e.floorName,e.labels]),M(Y(this._config?.collection_key)),this._labels.filter_rooms])}_renderIfChanged(){this._signature()!==this._drawn&&this._render()}disconnectedCallback(){this._unfilter?.(),this._unfilter=null}get _labels(){return b(this._hass)}_devices(){return y(this._hass).filter(e=>!e.untracked)}_allDevices(){return y(this._hass)}_optionsFor({kind:e,id:r,name:o},s){let a=new Map,n=!1;for(let c of s)c[r]?a.set(c[r],c[o]??c[r]):n=!0;let i=[...a.entries()].map(([c,l])=>({value:M({kind:e,id:c}),text:l})).sort((c,l)=>c.text.localeCompare(l.text));return n&&i.push({value:M({kind:e,id:null}),text:this._labels.filter_unfiled}),i}_labelOptions(e){let r=ot(this._hass);return[...new Set(e.flatMap(s=>s.labels??[]))].map(s=>({value:M({kind:"label",id:s}),text:r[s]??s})).sort((s,a)=>s.text.localeCompare(a.text))}_deviceOptions(){return this._allDevices().map(e=>({value:M({kind:"device",id:e.key}),text:e.name})).sort((e,r)=>e.text.localeCompare(r.text))}_groups(){let e=this._devices(),r=Rs.map(s=>({label:this._labels[s.label],options:this._optionsFor(s,e)})),o=this._labelOptions(e);return o.length&&r.push({label:this._labels.filter_labels,options:o}),r.push({label:this._labels.filter_devices,options:this._deviceOptions()}),r.filter(s=>s.options.length>0)}_render(){let e=this._labels,r=this._devices();this._drawn=this._signature();let o=r.length?this._control(e):`<p class="message">${e.no_devices}</p>`;this.shadowRoot.innerHTML=`
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
      <ha-card>${o}</ha-card>
    `;let s=this.shadowRoot.querySelector("select");s&&(s.value=M(Y(this._config?.collection_key)),s.addEventListener("change",()=>at(this._config?.collection_key,$s(s.value))))}_control(e){let r=this._groups().map(o=>`<optgroup label="${g(o.label)}">${o.options.map(s=>`<option value="${g(s.value)}">${g(s.text)}</option>`).join("")}</optgroup>`).join("");return`<div class="body">
      <span class="label">${e.title_filter}</span>
      <select>
        <option value="${M({kind:"all",id:null})}">${g(e.filter_everything)}</option>
        ${r}
      </select>
    </div>`}},We=class extends h{},Ns=()=>{_(vr,We),f(br,ze,{name:"Home Energy Advisor: Filter",description:"Narrow every Home Energy Advisor card on the page to a room, a floor, a label or one device."})};Ns();var wr="hea-self-sufficiency-card",Er=`${wr}-editor`,xr=["energyUsed","energyFromGrid","energyFromGeneration","energyFromBattery"],Is={maximumFractionDigits:0},Ds=.005,Ke=class extends w{static titleKey="title_self_sufficiency";static chartTag="ha-gauge";static bearingCard={type:"energy-self-sufficiency-gauge"};static emptyKey="no_energy_in_period";static cardStyle=`
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
  `;static getConfigElement(){return document.createElement(Er)}getCardSize(){return 4}_isEmpty(){return this._totals().energyUsed<=0}_totals(){return(this._result?.devices??[]).reduce((e,r)=>{for(let o of xr)e[o]+=r[o];return e},Object.fromEntries(xr.map(e=>[e,0])))}_shares(){let e=this._totals(),r=e.energyUsed,o=i=>e[i]/r,s=o("energyFromGeneration"),a=o("energyFromBattery"),n=o("energyFromGrid");return{generation:s,battery:a,grid:n,unaccounted:Math.max(0,1-s-a-n)}}_body(e){let r=super._body(e);return!this._chartReady||this._isEmpty()?r:`${r}${this._breakdown(e)}`}_chartMarkup(){return`<ha-gauge></ha-gauge>
      <div class="headline">${this._labels.from_generation}</div>`}_breakdown(e){let{battery:r,grid:o,unaccounted:s}=this._shares();return`<div class="shares">${[{label:"from_battery",value:r},{label:"from_grid",value:o},{label:"unaccounted",value:s}].filter(({label:n,value:i})=>n!=="unaccounted"||i>Ds).map(({label:n,value:i})=>`
        <div class="share">
          <span class="label">${this._labels[n]}</span>
          <span class="value" data-share="${n}">${j(i,e)}</span>
        </div>`).join("")}</div>
      <div class="note">${this._labels.self_sufficiency_note}</div>`}_draw(e){e.min=0,e.max=100,e.value=this._shares().generation*100,e.label="%",e.formatOptions=Is,e.locale=this._hass?.locale}},Ye=class extends h{},Ls=()=>{_(Er,Ye),f(wr,Ke,{name:"Home Energy Advisor: Self-sufficiency",description:"What share of the selected period's energy came from the household's own generation."})};Ls();var kr="hea-sources-card",Ar=`${kr}-editor`,Ms=({energyFromGrid:t,energyUsed:e})=>e>0&&t>=0&&t<=e?t/e:void 0,Gs=[{field:"name",label:"device"},{field:"energyUsed",label:"energy",format:k},{field:"energyFromGrid",label:"grid",format:k},{field:"energyFromGeneration",label:"generation",format:k},{field:"energyFromBattery",label:"battery",format:k},{derive:Ms,label:"from_grid",format:j}],Sr={energy_used:{field:"energyUsed",label:"energy_used"},energy_from_grid:{field:"energyFromGrid",label:"from_grid"},energy_from_generation:{field:"energyFromGeneration",label:"from_generation"},energy_from_battery:{field:"energyFromBattery",label:"from_battery"}},Ve=class extends D{static titleKey="title_sources";static columns=Gs;static sorts=Sr;static defaultSort="energy_used";static getConfigElement(){return document.createElement(Ar)}},qe=class extends h{_extraSchema(){return ge(Sr,b(this._hass))}},Hs=()=>{_(Ar,qe),f(kr,Ve,{name:"Home Energy Advisor: Energy sources",description:"Grid, generation and battery behind each device's energy over the period."})};Hs();var Tr="hea-totals-card",Or=`${Tr}-editor`,Ps=[{key:"actualCost",label:"paid"},{key:"costAtGridPrice",label:"would_have_paid"},{key:"costSavings",label:"saved"}],Ze=class extends F{static titleKey="title_totals";static cardStyle=`${le}
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
  `;static getConfigElement(){return document.createElement(Or)}getCardSize(){return 3}_body(e){let r=this._result?.totals;return`<div class="figures">${Ps.map(({key:s,label:a})=>{let n=r?.[s],i=s==="costSavings"?S(n):"",c=i?` ${i}`:"";return`
        <div class="figure">
          <span class="label">${de(a)}${this._labels[a]}</span>
          <span class="value${c}" data-figure="${s}">${u(n,e)}</span>
          ${this._comparedTo(s,n,e)}
        </div>`}).join("")}</div>`}_comparedTo(e,r,o){let s=this._result?.totals?.before?.[e];if(!Number.isFinite(s)||!Number.isFinite(r))return"";let a=H(e,r-s);return`<span class="${a?`compare ${a}`:"compare"}" data-compare="${e}">${v(this._labels.compared,{change:G(r-s,o),before:u(s,o)})}</span>`}},Xe=class extends h{},js=()=>{_(Or,Xe),f(Tr,Ze,{name:"Home Energy Advisor: Totals",description:"What the selected period cost, what it would have cost at grid price, and the difference."})};js();
