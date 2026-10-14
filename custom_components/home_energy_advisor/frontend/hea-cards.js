var Or=[4,4,0,0],Fr=[0,0,4,4],Ze=t=>t!==null&&typeof t=="object"&&!Array.isArray(t),$r=t=>{let e=Ze(t)?t.value:t;return Array.isArray(e)?e[1]:e},ge=(t,e)=>{let r=Ze(t)?{...t}:{value:t};return{...r,itemStyle:{...r.itemStyle,...e}}},te=t=>{let e=Math.max(...t.map(({data:o})=>o.length),0),r=t.map(({data:o})=>[...o]);for(let o of Rr(t))for(let s=0;s<e;s++)Ir(r,s,o);return t.map((o,s)=>({...o,data:r[s]}))},Rr=t=>{let e=new Map;return t.forEach((r,o)=>{let s=r.stack??Symbol(o),a=e.get(s);a?a.push(o):e.set(s,[o])}),[...e.values()]},Ir=(t,e,r)=>{let o=!1,s=!1;for(let a=r.length-1;a>=0;a--){let n=r[a],i=t[n][e];if(i===void 0)continue;let c=$r(i);c?c>0&&!o?(t[n][e]=ge(i,{borderRadius:Or}),o=!0):c<0&&!s&&(t[n][e]=ge(i,{borderRadius:Fr}),s=!0):t[n][e]=ge(i,{borderWidth:0})}};var Xe="_energy",ye="energy_";var Nr=(t,e)=>{let r=t||(e?`${ye}${e}`:"");return r?r.startsWith(ye)?`_${r}`:`_${ye}${r}`:Xe},Dr=(t,e)=>typeof t=="string"&&t.startsWith(Xe)&&e!==null&&typeof e=="object"&&typeof e.subscribe=="function"&&"start"in e,Lr=(t=new Date)=>{let e=new Date(t);return e.setDate(e.getDate()-30),e.setHours(0,0,0,0),{start:e,end:t,fallback:!0}},Mr=t=>{let e=t?.connection;if(!e)return{};let r={};for(let o of Object.keys(e)){let s;try{s=e[o]}catch{continue}Dr(o,s)&&(r[o]=s)}return r},Gr=(t,e)=>{let r=Mr(t),o=Nr(e,t?.panelUrl);if(r[o])return r[o];let[s]=Object.values(r);return s??null},Hr=t=>t?.startCompare&&t?.endCompare?{compare:{start:t.startCompare,end:t.endCompare,mode:t.compareMode}}:{},Qe=(t,e,r)=>{let o=null,s=null,a=0,n=t,i=l=>{if(o)return!0;let u=Gr(l,e);if(!u)return!1;let p=x=>r({start:u.start,end:u.end,fallback:!1,...Hr(x)});return o=u.subscribe(p),p(),!0},c=()=>{s=setTimeout(()=>{s=null,a+=1,!i(n)&&a<40&&c()},250)};return r(Lr()),i(t)||c(),{retry:l=>(l&&(n=l),i(n)),unsubscribe:()=>{s&&clearTimeout(s),s=null;try{typeof o=="function"&&o()}catch{}o=null}}};var re="sensor.home_energy_advisor_devices",Pr="home_energy_advisor",oe=t=>{if(t?.states?.[re])return re;let e=t?.entities;if(!e)return re;for(let[r,o]of Object.entries(e))if(o?.platform===Pr&&Array.isArray(t?.states?.[r]?.attributes?.devices))return r;return re},y=(t,e=void 0)=>{let r=t?.states?.[e??oe(t)]?.attributes?.devices;return Array.isArray(r)?r.filter(o=>o?.key).map(rt):[]},Je=(t,e=void 0)=>{let r=t?.states?.[e??oe(t)]?.attributes?.whole_home;return r?.key?rt(r):null},et=(t,e=void 0)=>{let r=t?.states?.[e??oe(t)]?.attributes?.settled_until;if(typeof r!="string")return null;let o=new Date(r);return Number.isNaN(o.getTime())?null:o},tt=(t,e=void 0)=>{let r=t?.states?.[e??oe(t)]?.attributes?.labels;return r&&typeof r=="object"?r:{}},rt=t=>({key:t.key,name:t.name||t.key,deviceId:t.device_id??null,untracked:!!t.untracked,statistics:t.statistics??{},areaId:t.area_id??null,areaName:t.area_name??null,floorId:t.floor_id??null,floorName:t.floor_name??null,upstream:t.upstream??null,labels:Array.isArray(t.labels)?t.labels:[]});var ot=Object.freeze({kind:"all",id:null}),jr={area:"areaId",floor:"floorId"},be=new Map,ve=t=>(be.has(t)||be.set(t,{filter:ot,listeners:new Set}),be.get(t)),W=t=>ve(t).filter,se=(t,e)=>{let{listeners:r}=ve(t);return r.add(e),()=>r.delete(e)},st=(t,e)=>{let r=ve(t),o={kind:e?.kind??"all",id:e?.id??null};if(!(o.kind===r.filter.kind&&o.id===r.filter.id)){r.filter=o;for(let s of r.listeners)try{s(o)}catch(a){console.warn("home-energy-advisor: a card could not follow the filter",a)}}},nt=(t,e)=>{let{kind:r,id:o}=e??ot;if(r==="all")return!0;if(r==="device")return t.key===o;if(t.untracked)return!1;if(r==="label")return(t.labels??[]).includes(o);let s=jr[r];return s?(t[s]??null)===o:!0};var Ur={day:"numeric",month:"short",year:"numeric"},ne=t=>({language:t?.locale?.language||void 0,currency:t?.config?.currency||void 0,timeFormat:t?.locale?.time_format||void 0,timeZone:t?.locale?.time_zone==="server"?t?.config?.time_zone:void 0}),Br=({timeFormat:t,language:e})=>{if(t==="language"||t==="system"||!t){let r=t==="system"?void 0:e;return new Date("January 1, 2023 22:00:00").toLocaleString(r).includes("10")}return t==="12"},at=(t,e)=>new Intl.DateTimeFormat(e.language,{hour:"numeric",minute:"2-digit",hourCycle:Br(e)?"h12":"h23",timeZone:e.timeZone}).format(t),zr=(t,e)=>new Intl.DateTimeFormat(e.language,{weekday:"short",month:"short",day:"numeric",timeZone:e.timeZone}).format(t),Wr={hour:3600*1e3},it=(t,e,r)=>{let o=Wr[e];if(!o)return zr(t,r);let s=new Date(t.getTime()+o);return`${at(t,r)} \u2013 ${at(s,r)}`},d=(t,{language:e,currency:r})=>{if(typeof t!="number"||!Number.isFinite(t))return"-";let o=r?{style:"currency",currency:r}:{minimumFractionDigits:2,maximumFractionDigits:2};return new Intl.NumberFormat(e,o).format(t)},G=(t,{language:e,currency:r})=>{if(typeof t!="number"||!Number.isFinite(t))return"-";let o=r?{style:"currency",currency:r,signDisplay:"exceptZero"}:{minimumFractionDigits:2,maximumFractionDigits:2,signDisplay:"exceptZero"};return new Intl.NumberFormat(e,o).format(t)},Kr=new Set(["actualCost","costAtGridPrice","energyUsed"]),Yr=new Set(["costSavings"]),T=t=>typeof t!="number"||!Number.isFinite(t)||t===0?"":t>0?"gain":"loss",H=(t,e)=>typeof e!="number"||!Number.isFinite(e)||e===0?"":Kr.has(t)?e<0?"gain":"loss":Yr.has(t)?e>0?"gain":"loss":"",I=(t,e)=>{if(!Array.isArray(t))return"-";let[r,o]=t;if(![r,o].every(n=>Number.isFinite(n)))return"-";if(r===o)return d(r,e);let[s,a]=r<=o?[r,o]:[o,r];return`${d(s,e)} - ${d(a,e)}`},k=(t,{language:e})=>typeof t!="number"||!Number.isFinite(t)?"-":`${new Intl.NumberFormat(e,{maximumFractionDigits:1}).format(t)} kWh`,ct={EUR:{symbol:"c",per:100},USD:{symbol:"\xA2",per:100},GBP:{symbol:"p",per:100}},K=(t,{language:e})=>typeof t!="number"||!Number.isFinite(t)?"-":new Intl.NumberFormat(e,{minimumFractionDigits:t===0?0:2,maximumFractionDigits:2}).format(t),Y=({language:t,currency:e})=>e?lt(t,e):"",lt=(t,e)=>new Intl.NumberFormat(t,{style:"currency",currency:e}).formatToParts(0).find(r=>r.type==="currency")?.value??"",dt=({language:t,currency:e})=>{if(!e)return"/kWh";let r=ct[e];return`${r?r.symbol:lt(t,e)}/kWh`},ut=(t,{language:e,currency:r})=>{if(typeof t!="number"||!Number.isFinite(t))return"-";let o=r?ct[r]:void 0;return new Intl.NumberFormat(e,{minimumFractionDigits:o?1:0,maximumFractionDigits:o?2:3}).format(o?t*o.per:t)},P=(t,{language:e})=>typeof t!="number"||!Number.isFinite(t)?"-":new Intl.NumberFormat(e,{style:"percent",maximumFractionDigits:0}).format(t),g=t=>String(t).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#39;"),V=(t,{language:e})=>t?new Intl.DateTimeFormat(e,Ur).formatRange(t.start,t.end):"";var mt="common",pt="home_energy_advisor",ht=`component.${pt}.${mt}.card_`,we=Object.freeze({paid:"Paid",would_have_paid:"Would have paid",saved:"Saved",lost:"Lost",paid_with_forgone:"Cost of use",range_column:"Paid (min-max)",range_note:"Paid (min-max) is the widest range these readings allow, not a typical error: a meter that reports every 30-90 minutes leaves the exact moment of use unknown.",range_whole_home:"What you paid could honestly sit between {range} - the widest these readings allow, not a typical error.",range_device:"What you paid could be between {range}.",range_note_rollover:"Hover over or tap a figure in Paid to see the range it could honestly have been. That range is the widest these readings allow, not a typical error: a meter that reports every 30-90 minutes leaves the exact moment of use unknown.",range_note_cost_of_use:"Hover over or tap a figure in Cost of use to see what it is made of: what you paid, with the range it could honestly have been, plus what your own generation could have earned by exporting instead, at your export rate at the time. That second part is not money you paid, but money you did not receive. The range covers only what you paid. It is the widest these readings allow, not a typical error: a meter that reports every 30-90 minutes leaves the exact moment of use unknown.",range_note_not_cost_of_use:"It ranges what you paid, not Cost of use, which is what you paid plus Forgone export.",forgone_column:"Forgone export",paid_breakdown:"Paid {paid} ({range}) + {forgone} your generation could have earned",paid_breakdown_unranged:"Paid {paid} + {forgone} your generation could have earned",compared:"{change} vs {before}",compared_period:"{period} vs {compared}",saved_share:"{percent} of what you would have paid was saved.",lost_share:"{percent} more was paid than the grid would have cost.",change:"Change",compared_series:"Earlier period",device:"Device",energy:"Energy",rate:"Rate",total:"Total",grid:"Grid",generation:"Generation",battery:"Battery",from_grid:"From the grid",from_generation:"From generation",from_battery:"From the battery",energy_used:"Energy used",unaccounted:"Unaccounted",self_sufficiency_note:"Battery energy is counted on its own: it was charged from generation or from the grid, and these readings cannot say which.",household:"Household",title_totals:"Cost summary",title_devices:"Cost by device",title_device_costs:"What each device cost",title_cost_over_time:"Cost over time",title_sources:"Where the energy came from",title_self_sufficiency:"Self-sufficiency",title_distribution:"Where the cost went",title_distribution_energy:"Where the energy went",no_devices:"No devices are being tracked yet.",no_devices_in_filter:"No tracked device matches what the page is showing.",title_filter:"Show",filter_everything:"Everything",filter_rooms:"Rooms",filter_floors:"Floors",filter_labels:"Labels",filter_devices:"Devices",filter_unfiled:"Not in one",device_untracked:"Untracked",hourly_shape_estimate:"One device's hourly shape is an estimate: each meter reading is spread across the hours it spanned, so cost may not land in the hour the energy was used.",still_accruing:"The last interval is still being counted, so its bar will grow. Figures are complete about twenty minutes behind the clock, which is how long meters are given to report.",statistics_failed:"Statistics could not be loaded.",no_picker:"Add an Energy date picker card to choose the range.",chart_not_loaded:"Home Assistant's chart component is not loaded. Adding any energy or statistics card to this dashboard will load it.",no_cost_in_period:"No cost recorded in this period.",no_energy_in_period:"No energy recorded in this period.",editor_title:"Title",editor_collection_key:"Energy period (collection key)",editor_devices:"Devices (all, if none are chosen)",editor_sort_by:"Order by",editor_layout:"Layout",editor_metric:"Measure by",editor_forgone:"Count what your own generation could have earned",editor_forgone_include:"Include it in the cost",editor_forgone_exclude:"Show only what you paid",editor_range:"Show the cost range as",editor_range_rollover:"A rollover on Paid",editor_range_column:"Its own column"}),xe=new Map,ft=new Map,_t=t=>t?.locale?.language||t?.language||"en",A=t=>{let e=_t(t);return xe.has(e)||xe.set(e,Vr(t,e).then(r=>(ft.set(e,r),r))),xe.get(e)},Vr=async(t,e)=>{try{let{resources:r}=await t.callWS({type:"frontend/get_translations",language:e,category:mt,integration:[pt]});return Object.freeze({...we,...qr(r)})}catch(r){return console.warn("home-energy-advisor: falling back to English labels",r),we}},v=t=>ft.get(_t(t))??we,qr=t=>Object.fromEntries(Object.entries(t??{}).filter(([e,r])=>e.startsWith(ht)&&r).map(([e,r])=>[e.slice(ht.length),r])),b=(t,e)=>Object.entries(e).reduce((r,[o,s])=>r.replaceAll(`{${o}}`,s),t);var j=Object.freeze({energyUsed:"energy_used",actualCost:"actual_cost",costAtGridPrice:"cost_at_grid_price",energyFromGrid:"energy_from_grid",energyFromGeneration:"energy_from_generation",energyFromBattery:"energy_from_battery",forgoneExport:"forgone_export"}),C=Object.freeze({costFloor:"lowest_possible_cost",costCeiling:"highest_possible_cost"}),Ee=()=>Object.fromEntries(Object.keys(j).map(t=>[t,0])),bt=1440*60*1e3,vt={hour:3600*1e3,day:bt},Zr=2,q=(t,e)=>t?.statistics?.[e],Xr=(t,e)=>{let r=t.flatMap(o=>[...Object.values(j),...Object.values(C)].map(s=>q(o,s)).filter(Boolean));return!e?.statistics||t.length===0?r:[...r,...Object.values(C).map(o=>q(e,o)).filter(Boolean)]},xt=(t,e)=>{if(!e)return t;let r=new Map(e.devices.map(o=>[o.key,o]));return{...t,totals:{...t.totals,before:e.totals},devices:t.devices.map(o=>({...o,before:r.get(o.key)})),seriesBefore:Qr(e.series,t.period,e.period)}},Qr=(t,e,r)=>{if(!t?.length)return;let o=e.start.getTime()-r.start.getTime();return t.map(s=>({...s,start:new Date(s.start.getTime()+o),actualStart:s.start}))},O=({start:t,end:e})=>e-t>Zr*bt?"day":"hour",gt=(t,e,r)=>{if(e!=="day")return new Date(t.getTime()+r*vt.hour);let o=new Date(t);return o.setDate(o.getDate()+r),o},wt=(t,e)=>{if(!t.length||!e)return t;let r=O(e),o=new Map(t.map(n=>[n.start.getTime(),n])),s=t[0].start,a=[];for(let n=0;;n--){let i=gt(s,r,n);if(i.getTime()<e.start.getTime())break;a.push(o.get(i.getTime())??yt(i))}a.reverse();for(let n=1;;n++){let i=gt(s,r,n);if(i.getTime()>=e.end.getTime())break;a.push(o.get(i.getTime())??yt(i))}return a},yt=t=>({...Ee(),start:t,costSavings:0,accruing:!1}),ke=async(t,e,r,o,s=null)=>{let a=Xr(e,o),n=a.length?await t.callWS({type:"recorder/statistics_during_period",start_time:r.start.toISOString(),end_time:r.end.toISOString(),statistic_ids:a,period:O(r),types:["change"]}):{},i=e.map(c=>eo(c,n,r));return{period:r,devices:i,totals:to(i),wholeHome:Et(o,n,r),series:Jr(e,n,r,s)}},Et=(t,e,r)=>{if(!t)return;let o={};for(let[s,a]of Object.entries(C)){let n=e?.[q(t,a)];if(!Array.isArray(n))return;o[s]=St(n,r)}return o},Jr=(t,e,r,o)=>{let s=new Map;for(let n of t)for(let[i,c]of Object.entries(j)){let l=e?.[q(n,c)];for(let u of kt(l,r)){let p=s.get(u.start)??Ee();p[i]+=u.change,s.set(u.start,p)}}let a=vt[O(r)]??0;return[...s.entries()].sort(([n],[i])=>n-i).map(([n,i])=>({...i,start:new Date(n),costSavings:i.costAtGridPrice-i.actualCost,accruing:o?n+a>o.getTime():!1}))},eo=(t,e,r)=>{let o=Object.fromEntries(Object.entries(j).map(([s,a])=>[s,St(e?.[q(t,a)],r)]));return{...t,...o,...Et(t,e,r),costSavings:o.costAtGridPrice-o.actualCost}},kt=(t,{start:e,end:r})=>{if(!Array.isArray(t))return[];let o=[];for(let s of t){let a=new Date(s.start).getTime();a<e.getTime()||a>=r.getTime()||typeof s.change=="number"&&o.push({start:a,change:s.change})}return o},St=(t,e)=>kt(t,e).reduce((r,o)=>r+o.change,0),to=t=>({...t.reduce((r,o)=>{for(let s of Object.keys(r))r[s]+=o[s];return r},{...Ee(),costSavings:0}),...ro(t)}),ro=t=>{let e=Object.keys(C);return!t.length||!t.every(r=>e.every(o=>o in r))?{}:Object.fromEntries(e.map(r=>[r,t.reduce((o,s)=>o+s[r],0)]))};var oo=`
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
`,F=class extends HTMLElement{static cardStyle="";static titleKey="";_titleKey(){return this.constructor.titleKey}get _labels(){return v(this._hass)}constructor(){super(),this.attachShadow({mode:"open"}),this._state="loading",this._request=0}setConfig(e){if(e.devices!==void 0&&!Array.isArray(e.devices))throw new Error("`devices` must be a list of device keys");this._config=e,this._render()}set hass(e){this._hass=e,this._subscription?this._subscription.retry(e):this._subscribe(),this._refetchIfDevicesChanged()}connectedCallback(){this._render(),this._hass&&!this._subscription&&this._subscribe()}disconnectedCallback(){this._subscription?.unsubscribe(),this._subscription=null,this._unfilter?.(),this._unfilter=null}_subscribe(){this._subscription=Qe(this._hass,this._config?.collection_key,e=>{this._period=e,this._scheduleFetch()}),this._unfilter=se(this._config?.collection_key,()=>this._scheduleFetch())}_scheduleFetch(){this._fetchPending||(this._fetchPending=!0,queueMicrotask(()=>{this._fetchPending=!1,this._fetch()}))}_refetchIfDevicesChanged(){let e=this._devices().map(r=>r.key).join(",");e!==this._deviceKeys&&(this._deviceKeys=e,this._period&&this._scheduleFetch())}_devices(){let e=y(this._hass),r=this._config?.devices,o=r?e.filter(a=>r.includes(a.key)):e,s=this._filter();return o.filter(a=>nt(a,s))}_filter(){return W(this._config?.collection_key)}_isFiltered(){return!!this._config?.devices||this._filter().kind!=="all"}async _fetch(){if(!this._hass||!this._period)return;let e=this._devices(),r=++this._request;if(await A(this._hass),e.length===0){this._state="empty",this._render();return}let o=this._isFiltered()?void 0:Je(this._hass);try{let s=et(this._hass),[a,n]=await Promise.all([ke(this._hass,e,this._period,o,s),this._period.compare?ke(this._hass,e,this._period.compare,o):void 0]);if(r!==this._request)return;this._result=xt(a,n),this._state="ready"}catch(s){if(r!==this._request)return;this._state="error",console.error(`${this.localName}: could not load statistics`,s)}this._render()}_render(){let e=ne(this._hass);this.shadowRoot.innerHTML=`
      <style>${oo}${this.constructor.cardStyle}${so}</style>
      <ha-card>
        <div class="body" data-state="${this._state}">${this._content(e)}</div>
      </ha-card>
    `;let r=this._config?.title??this._labels[this._titleKey()];r&&this._writeHeader(r,e),this._afterRender()}_writeHeader(e,r){let o=this.shadowRoot.querySelector("ha-card"),s=this._headerChip(r);if(s===void 0){o.setAttribute("header",e);return}o.insertAdjacentHTML("afterbegin",`<div class="card-header" style="display: flex; justify-content: space-between;
         align-items: center; gap: var(--hea-space-s); padding-bottom: 0;">
        <span class="title">${g(e)}</span>
        <span class="chip">${g(s)}</span>
      </div>`)}_headerChip(){}_afterRender(){}_content(e){return this._state==="empty"?`<p class="message">${this._labels.no_devices}</p>`:this._state==="error"?`<p class="message">${this._labels.statistics_failed}</p>`:`${this._body(e)}${this._caption(e)}`}_caption(e){let r=this._period?.fallback?`<div class="hint">${this._labels.no_picker}</div>`:"";return`<div class="period">${this._periodLabel(e)}</div>${r}`}_periodLabel(e){let r=V(this._period,e),o=this._period?.compare;return o?b(this._labels.compared_period,{period:r,compared:V(o,e)}):r}},f=(t,e,{name:r,description:o})=>{customElements.get(t)||customElements.define(t,e),globalThis.customCards=globalThis.customCards??[],globalThis.customCards.some(s=>s.type===t)||globalThis.customCards.push({type:t,name:r,description:o})};var no={title:"editor_title",collection_key:"editor_collection_key",devices:"editor_devices",sort_by:"editor_sort_by",layout:"editor_layout",metric:"editor_metric",range:"editor_range"},m=class extends HTMLElement{constructor(){super(),this.attachShadow({mode:"open"})}setConfig(e){this._config=e,this._render()}set hass(e){this._hass=e,this._render(),A(e).then(()=>this._render())}_extraSchema(){return[]}_render(){if(!this._config)return;let e=this.shadowRoot.querySelector("ha-form");e||(e=document.createElement("ha-form"),e.computeLabel=r=>v(this._hass)[no[r.name]]??r.name,e.addEventListener("value-changed",r=>this._report(r.detail.value)),this.shadowRoot.append(e)),e.hass=this._hass,e.data=this._config,e.schema=this._schema()}_schema(){return[{name:"title",selector:{text:{}}},{name:"collection_key",selector:{text:{}}},{name:"devices",selector:{select:{multiple:!0,mode:"list",options:y(this._hass).map(e=>({value:e.key,label:e.name}))}}},...this._extraSchema()]}_report(e){this.dispatchEvent(new CustomEvent("config-changed",{detail:{config:ao({...this._config,...e})},bubbles:!0,composed:!0}))}},ao=t=>Object.fromEntries(Object.entries(t).filter(([,e])=>e!==""&&e!==void 0&&e!==null&&!(Array.isArray(e)&&e.length===0))),_=(t,e)=>{customElements.get(t)||customElements.define(t,e)};var w=class extends F{static chartTag="ha-chart-base";static bearingCard={type:"statistics-graph",entities:[]};static emptyKey="no_cost_in_period";static chartHeight="clamp(320px, 40vw, 480px)";static cardStyle=`
    ha-chart-base { display: block; --chart-max-height: none; }
  `;constructor(){super(),this._chartReady=!!customElements.get(this.constructor.chartTag)}getCardSize(){return 6}static narrowQuery="";connectedCallback(){super.connectedCallback(),this._chartReady||this._loadChartComponent(),this._watchScreen()}disconnectedCallback(){super.disconnectedCallback(),this._screen?.removeEventListener?.("change",this._onScreenChange),this._screen=null}_watchScreen(){let{narrowQuery:e}=this.constructor;!e||this._screen||(this._screen=globalThis.matchMedia?.(e),this._onScreenChange??=()=>this._render(),this._screen?.addEventListener?.("change",this._onScreenChange))}async _loadChartComponent(){let{chartTag:e,bearingCard:r}=this.constructor;customElements.whenDefined(e).then(()=>{this._chartReady=!0,this._render()});try{await(await globalThis.loadCardHelpers?.())?.createCardElement(r)}catch(o){console.warn(`${e}: could not be loaded`,o)}}_isEmpty(){return(this._result?.series??[]).length===0}_body(){return this._chartReady?this._isEmpty()?`<p class="message">${this._labels[this._emptyKey()]}</p>`:this._chartMarkup():`<p class="message">${this._labels.chart_not_loaded}</p>`}_emptyKey(){return this.constructor.emptyKey}_chartMarkup(){return'<ha-chart-base chart-type="bar"></ha-chart-base>'}_afterRender(){let e=this.shadowRoot.querySelector(this.constructor.chartTag);e&&(e.hass=this._hass,this._draw(e))}_chartHeight(){return this.constructor.chartHeight}_draw(e){e.height=this._chartHeight(),e.data=this._series(),e.options=this._options(this._chartLocale())}_chartLocale(){return ne(this._hass)}_colour({variable:e,fallback:r}){return getComputedStyle(this).getPropertyValue(e).trim()||r}};var io=/^#([\da-f]{3}|[\da-f]{6})$/i,co=/^rgba?\(([^)]+)\)$/i,Se=t=>{let e=io.exec(String(t).trim());if(e){let s=e[1];return(s.length===3?[...s].map(n=>n+n):[0,2,4].map(n=>s.slice(n,n+2))).map(n=>Number.parseInt(n,16))}let r=co.exec(String(t).trim());if(!r)return;let o=r[1].split(/[\s,/]+/).filter(Boolean).slice(0,3).map(Number);return o.length===3&&o.every(Number.isFinite)?o:void 0},S=(t,e)=>{let r=Se(String(t).trim());return r?`rgba(${r.join(", ")}, ${e})`:t},lo=([t,e,r])=>(.2126*t+.7152*e+.0722*r)/255,ae=t=>{let e=Se(uo(t));return e?lo(e)>.5:!1},uo=t=>{let e=[t,t?.ownerDocument?.documentElement].filter(Boolean);for(let r of e){let o=getComputedStyle(r),s=o.getPropertyValue("--primary-text-color").trim()||o.color;if(Se(s))return s}return""};var Tt=Object.freeze({variable:"--primary-color",fallback:"#03a9f4"}),At=Object.freeze({variable:"--success-color",fallback:"#4caf50"}),ho=Object.freeze({paid:"paid",would_have_paid:"would-have-paid",saved:"saved"}),ie=`
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
`,ce=t=>{let e=typeof t=="string"?ho[t]:void 0;return e?`<span class="swatch ${e}" aria-hidden="true"></span>`:""};var $=(t,e,r,{bold:o=!1}={})=>{let s=document.createElement("div");s.style.display="flex",s.style.justifyContent="space-between",s.style.gap="16px",o&&(s.style.fontWeight="bold");let a=document.createElement("span");a.textContent=t;let n=document.createElement("span");return n.textContent=e,n.style.fontVariantNumeric="tabular-nums",r&&(n.style.color=r),s.append(a,n),s},mo=t=>{let e=document.createElement("span");return e.style.display="inline-block",e.style.width="10px",e.style.height="10px",e.style.borderRadius="10px",e.style.marginInlineEnd="4px",e.style.verticalAlign="middle",e.style.backgroundColor=t,e},Ct=(t,e,r,o)=>{let s=$(e,r,o);return s.firstChild.prepend(mo(t)),s},le=t=>{let e=document.createElement("div");return e.textContent=t,e.style.fontWeight="bold",e.style.textAlign="center",e.style.marginBottom="4px",e},Ot=t=>{let e=document.createElement("div");return e.textContent=t,e.style.marginTop="4px",e.style.maxWidth="260px",e.style.whiteSpace="normal",e.style.opacity="0.7",e};var It="hea-cost-over-time-card",Nt=`${It}-editor`,po={hour:3600*1e3,day:1440*60*1e3},fo=50,_o=.5,go=(t,e)=>{if(!t.length||!e)return 0;let r=po[O(e)]??0,o=t.length>=2?t[1].start.getTime()-t[0].start.getTime():void 0;return(o?Math.min(o,r):r)/2},R={paid:{id:"paid",name:"paid",...Tt},saved:{id:"saved",name:"saved",...At}},Dt={variable:"--error-color",fallback:"#db4437"},yo={gain:{variable:"--success-color",fallback:"#4caf50"},loss:Dt},Te=t=>t.value?.[1]??0,bo=t=>t.value?.[2],vo=.45,de={id:"before",name:"compared_series",variable:"--secondary-text-color",fallback:"#727272"},Ae=class extends w{static titleKey="title_cost_over_time";static getConfigElement(){return document.createElement(Nt)}_series(){let e=wt(this._result?.series??[],this._result?.period),r=this._colour(Dt),o=this._labels,s=this._result?.seriesBefore,a=go(e,this._result?.period);return[...te([{...Rt(R.paid,this._colour(R.paid),o),data:e.map(n=>Ft(n,$t(n,n.actualCost,a)))},{...Rt(R.saved,this._colour(R.saved),o),data:e.map(n=>{let i=$t(n,n.costSavings,a),c=n.costSavings<0?Lt(r):void 0;return Ft(n,i,c)})}]),...s?.length?[{id:de.id,name:o[de.name],type:"line",symbol:"none",lineStyle:{type:"dashed",width:2},itemStyle:{color:this._colour(de)},data:s.map(n=>[n.start.getTime()+a,n.costAtGridPrice])}]:[]]}_caption(e){return`${super._caption(e)}${this._stillAccruingNote()}`+this._accrualNote()}_stillAccruingNote(){return(this._result?.series??[]).some(e=>e.accruing)?`<div class="hint">${this._labels.still_accruing}</div>`:""}_accrualNote(){return this._devices().length!==1||!this._period||O(this._period)!=="hour"?"":`<div class="hint">${this._labels.hourly_shape_estimate}</div>`}_tooltipFor(e,r){let o=(Array.isArray(e)?e:[e]).filter(c=>c.componentSubType==="bar"),s=o.filter(c=>Te(c)!==0);if(!s.length)return;let a=this._bucketAt(o.map(bo).find(c=>c!==void 0)),n=document.createElement("div");n.append(le(this._spanOf(a,r)));for(let c of s)n.append(this._tooltipRowFor(c,r));let i=o.reduce((c,l)=>c+Te(l),0);return s.length>1&&n.append($(this._labels.would_have_paid,d(i,r),void 0,{bold:!0})),a?.accruing&&n.append(Ot(this._labels.still_accruing)),n}_tooltipRowFor(e,r){let o=Te(e),a=e.seriesId===R.saved.id&&o<0?this._labels.lost:e.seriesName,n=e.seriesId===R.saved.id?T(o):"";return Ct(e.color,a,d(o,r),n?this._colour(yo[n]):void 0)}_bucketAt(e){if(e!==void 0)return(this._result?.series??[]).find(r=>r.start.getTime()===e)}_spanOf(e,r){return!e||!this._period?"":it(e.start,O(this._period),r)}_headerChip(e){let r=this._result?.totals?.actualCost;return Number.isFinite(r)&&!this._isEmpty()?d(r,e):""}_axisBounds(){if(!this._period)return{};let{start:e,end:r}=this._period,o=new Date(r.getTime()-1);return O(this._period)==="hour"?o.setMinutes(30,0,0):(o.getHours()===0&&o.setHours(o.getHours()-1),o.setHours(0,0,0,0)),{min:e.getTime(),max:o.getTime()}}_options(e){let r=this._labels;return{xAxis:{type:"time",...this._axisBounds()},grid:{top:15,bottom:0,left:1,right:1,containLabel:!0},yAxis:{type:"value",name:Y(e),nameGap:2,nameTextStyle:{align:"left"},boundaryGap:[0,0],splitNumber:5,splitLine:{show:!0},axisLabel:{formatter:o=>K(o,e),hideOverlap:!0}},tooltip:{trigger:"axis",axisPointer:{type:"shadow"},formatter:o=>this._tooltipFor(o,e)},legend:{show:!0,type:"custom",data:[R.paid,R.saved,...this._result?.seriesBefore?.length?[de]:[]].map(o=>({id:o.id,name:r[o.name],itemStyle:{color:this._colour(o)}}))}}}},Ft=(t,e,r=void 0)=>t.accruing?{value:e,itemStyle:{...r,opacity:vo}}:r?{value:e,itemStyle:r}:e,$t=(t,e,r)=>[t.start.getTime()+r,e,t.start.getTime()],Rt=({id:t,name:e},r,o)=>({id:t,name:o[e],type:"bar",stack:"cost",barMaxWidth:fo,itemStyle:Lt(r)}),Lt=t=>({color:S(t,_o),borderColor:t,borderWidth:1}),Ce=class extends m{},xo=()=>{_(Nt,Ce),f(It,Ae,{name:"Home Energy Advisor: Cost over time",description:"What the period cost, stacked against what it would have cost at grid price."})};xo();var $e="hea",Pt="Home Energy Advisor",wo="mdi:home-lightning-bolt",Mt=`ll-strategy-dashboard-${$e}`,Gt=`ll-strategy-view-${$e}`,Eo=[{type:"custom:hea-totals-card"},{type:"custom:hea-devices-card",sort_by:"actual_cost"},{type:"custom:hea-cost-over-time-card"},{type:"custom:hea-sources-card",sort_by:"energy_used"}],ko=[{type:"custom:hea-device-costs-card"},{type:"custom:hea-distribution-card"},{type:"custom:hea-self-sufficiency-card"}],So=t=>({...t,grid_options:{columns:"full",rows:"auto"}}),Ht=t=>({type:"grid",column_span:2,cards:t.map(So)}),To=()=>({card:{type:"horizontal-stack",cards:[{type:"energy-date-selection",vertical_opening_direction:"up"},{type:"custom:hea-filter-card"}]},max_width:1600}),Ao=t=>({type:"sections",max_columns:4,sections:[{type:"grid",cards:[{type:"markdown",content:v(t).no_devices}]}]}),Co=t=>y(t).length===0?Ao(t):{type:"sections",max_columns:4,sections:[Ht(Eo),Ht(ko)],footer:To()},jt=async t=>(await A(t),Co(t)),Oe=class extends HTMLElement{static async generate(e,r){return{views:[await jt(r)]}}static noEditor=!0;static getCreateSuggestions(){return{title:Pt,icon:wo}}},Fe=class extends HTMLElement{static async generate(e,r){return jt(r)}},Oo=t=>{globalThis.customStrategies=globalThis.customStrategies??[],globalThis.customStrategies.some(e=>e.type===t.type)||globalThis.customStrategies.push(t)},Fo=()=>{customElements.get(Mt)||customElements.define(Mt,Oe),customElements.get(Gt)||customElements.define(Gt,Fe),Oo({type:$e,strategyType:"dashboard",name:Pt,description:"What each device cost to run, and what solar and the battery saved."})};Fo();var Ut=Object.keys(j),$o=Object.keys(C),Bt=t=>{let e=new Map;for(let r of t){if(!r.upstream)continue;let o=e.get(r.upstream);o?o.push(r):e.set(r.upstream,[r])}return e},zt=(t,e)=>({...t,key:`${t.key}${Ro}`,name:`${t.name} ${e.device_untracked}`,upstream:t.key,untracked:!1,residualOf:t.key}),Ro="__untracked",Io=t=>{let e=Object.fromEntries(Ut.map(r=>[r,0]));for(let r of t)for(let o of Ut)e[o]+=r[o]??0;for(let r of $o)e[r]=t.every(o=>typeof o[r]=="number")?t.reduce((o,s)=>o+s[r],0):void 0;return e.costSavings=e.costAtGridPrice-e.actualCost,e},ue=(t,e)=>{let r=Bt(t);return r.size===0?t:t.flatMap(o=>r.has(o.key)?[zt(o,e)]:[o])},Wt=(t,e,r=o=>o)=>{let o=Bt(t);if(o.size===0)return r(t).map(n=>({device:n,depth:0}));let s=new Set(o.keys()),a=t.filter(n=>!n.upstream);return r(a).flatMap(n=>{if(!s.has(n.key))return[{device:n,depth:0}];let i=r([...o.get(n.key),zt(n,e)]);return[{device:{...n,...Io(i),subtotal:!0},depth:0},...i.map(c=>({device:c,depth:1}))]})};var E=Object.freeze(["#0072b2","#e69f00","#009e73","#cc79a7","#56b4e9","#d55e00","#8c6bb1","#3d9970"]),No=Object.freeze(["#4b46b3","#8d9b1f","#00a2ab","#b07ad2","#7fa0ee","#a8761b","#b26596","#5b8f3f"]),Re=Object.freeze([E,No]),wn=E.length*Re.length,U=Object.freeze({variable:"--secondary-text-color",fallback:"#8a8a8a"}),B=t=>{let e=(t??[]).filter(r=>!r.untracked).map(r=>r.key).sort(Do);return new Map(e.map((r,o)=>{let s=Math.floor(o/E.length)%Re.length;return[r,Re[s][o%E.length]]}))},Do=(t,e)=>t===e?0:t<e?-1:1;var he=(t,e,r)=>{let o=t<0?e.lost_share:e.saved_share;return b(o,{percent:P(Math.abs(t),r)})},Lo=({costSavings:t,costAtGridPrice:e})=>{if(!(!Number.isFinite(t)||!Number.isFinite(e))&&!(e<=0))return t/e},Z=[{at:0,hue:3,light:48,dark:62},{at:.5,hue:35,light:46,dark:68},{at:1,hue:142,light:31,dark:76}],Kt={light:85,dark:70},Mo=.7,Yt=(t,e,r)=>t+(e-t)*r,Go=.6,Ho=(t,e)=>{let r=Z.findIndex(i=>t<=i.at);if(r<=0)return{hue:Z[0].hue,lightness:Z[0][e]};let o=Z[r-1],s=Z[r],a=(t-o.at)/(s.at-o.at),n=r===1?a:a**Go;return{hue:Yt(o.hue,s.hue,n),lightness:Yt(o[e],s[e],a)}},Vt=.05,N=t=>Math.round(t*10)/10,me=(t,{dark:e=!1}={})=>{let r=e?"dark":"light",o=a=>Math.max(0,a?.costAtGridPrice??0),s=Math.max(0,...(t??[]).map(o));return a=>{let n=Lo(a??{});if(n===void 0||s<=0)return;let i=Math.min(1,o(a)/s),c=i*(1+Vt)/(i+Vt),l=Math.min(1,Math.max(0,n)),{hue:u,lightness:p}=Ho(l,r),x=Kt[r]*c**Mo;return{rate:n,text:`hsl(${N(u)}, ${N(x)}%, ${N(p)}%)`,edge:`hsla(${N(u)}, ${N(Kt[r])}%, ${N(p)}%, ${N(c)})`}}};var rr="hea-device-costs-card",or=`${rr}-editor`,qt={variable:"--error-color",fallback:"#db4437"},Po={variable:"--secondary-text-color",fallback:"#727272"},jo="earlier-period",Uo=["auto","vertical","horizontal"],Zt="(max-width: 767px)",Bo="paid",zo="saved",Xt="before",Wo=30,Ko=46,Yo=64,Vo=240,qo=24,Zo=12,Xo=2,Qo=10,Jo=300,es=120,ts="40vw",rs={left:8,right:16,top:8,bottom:28,containLabel:!0},Qt=1.5,Jt=.8,er=.45,tr=.22,os=/:(?:paid|saved|before)$/,ss={gain:{variable:"--success-color",fallback:"#4caf50"},loss:{variable:"--error-color",fallback:"#db4437"}},ns=(t,e,r,o,s,a)=>{let n=T(t.costSavings),i=document.createElement("div");i.append(le(e),$(o.paid,d(t.actualCost,r)),$(t.costSavings<0?o.lost:o.saved,d(t.costSavings,r),n?s(n):void 0),$(o.would_have_paid,d(t.costAtGridPrice,r)));let c=as(a,r,o);c&&i.append(c);let l=is(t,r,o,s);l&&i.append(l);let u=cs(t,r,o);return u&&i.append(u),i},as=(t,e,r)=>{if(!t)return;let o=document.createElement("div");return o.style.marginTop="4px",o.style.color=t.text,o.textContent=he(t.rate,r,e),o},is=(t,e,r,o)=>{let s=t.before?.actualCost;if(!Number.isFinite(s)||!Number.isFinite(t.actualCost))return;let a=t.actualCost-s,n=H("actualCost",a);return $(r.change,b(r.compared,{change:G(a,e),before:d(s,e)}),n?o(n):void 0)},cs=({costFloor:t,costCeiling:e},r,o)=>{if(![t,e].every(a=>Number.isFinite(a)))return;let s=document.createElement("div");return s.style.marginTop="4px",s.style.opacity="0.75",s.textContent=b(o.range_device,{range:I([t,e],r)}),s},Ie=class extends w{static titleKey="title_device_costs";static narrowQuery=Zt;static getConfigElement(){return document.createElement(or)}_isEmpty(){return this._ranked().every(e=>!e.costAtGridPrice&&!e.actualCost)}_ranked(){return ue(this._result?.devices??[],this._labels).sort((e,r)=>r.actualCost-e.actualCost||e.name.localeCompare(r.name))}_colourFor(e){if(e.untracked)return this._colour(U);let r=e.residualOf??e.key;return this._colours().get(r)??E[0]}_colours(){return B(y(this._hass))}_verdicts(){return me(this._ranked(),{dark:ae(this)})}_sideways(){let e=this._config?.layout;return e==="horizontal"?!0:e==="vertical"?!1:!!globalThis.matchMedia?.(Zt)?.matches}_comparing(){return this._ranked().some(e=>e.before)}_series(){return te(this._sideways()?this._sidewaysSeries():this._standingSeries())}_sidewaysSeries(){let e=this._ranked(),r=this._colour(qt),o=this._labels,s=a=>this._colourFor(a);return[{id:Bo,name:o.paid,type:"bar",stack:"cost",data:e.map(a=>({value:a.actualCost,itemStyle:{color:S(s(a),Jt)}}))},{id:zo,name:o.saved,type:"bar",stack:"cost",data:e.map(a=>{let n=a.costSavings<0?r:s(a);return{value:a.costSavings,itemStyle:{color:S(n,tr),borderColor:n,borderWidth:Qt}}})},...this._comparing()?[{id:Xt,name:o.compared_series,type:"bar",stack:"earlier",data:e.map(a=>({value:a.before?a.before.actualCost:null,itemStyle:{color:S(s(a),er)}}))}]:[]]}_standingSeries(){let e=this._colour(qt);return this._ranked().flatMap(r=>{let o=this._colourFor(r),s=r.costSavings<0?e:o,a=r.name;return[{id:`${r.key}:paid`,name:a,type:"bar",stack:r.key,itemStyle:{color:S(o,Jt)},data:[r.actualCost]},{id:`${r.key}:saved`,name:a,type:"bar",stack:r.key,itemStyle:{color:S(s,tr),borderColor:s,borderWidth:Qt},data:[r.costSavings]},...r.before?[{id:`${r.key}:before`,name:a,type:"bar",stack:`${r.key}:before`,itemStyle:{color:S(o,er)},data:[r.before.actualCost]}]:[]]})}_tooltipFor({seriesId:e,dataIndex:r},o){let s=this._ranked(),a=this._sideways()?s[r]:s.find(n=>n.key===String(e??"").replace(os,""));return a?ns(a,a.name,o,this._labels,n=>this._colour(ss[n]),this._verdicts()(a)):void 0}_earlierKey(){if(!this._comparing())return[];let e=this._labels.compared_series,r={color:this._colour(Po)};return this._sideways()?[{id:Xt,name:e,itemStyle:r}]:[{id:jo,secondaryIds:this._ranked().filter(o=>o.before).map(o=>`${o.key}:before`),name:e,itemStyle:r}]}_chartHeight(){if(this._sideways()){let r=this._ranked().length,o=this._comparing()?Ko:Wo;return`${Math.max(Vo,Yo+r*o)}px`}let e=Jo+this._legendHeight();return`clamp(${e}px, ${ts}, ${e+es}px)`}_legendHeight(){let e=Math.min(this._ranked().length,Qo)+this._earlierKey().length;return Math.ceil(e/Xo)*qo+Zo}_options(e){return this._sideways()?this._sidewaysOptions(e):this._standingOptions(e)}_sidewaysOptions(e){let r=this._earlierKey();return{xAxis:{type:"value",name:Y(e),axisLabel:{formatter:o=>K(o,e),hideOverlap:!0}},yAxis:{type:"category",data:this._ranked().map(o=>o.name),inverse:!0},grid:rs,tooltip:{trigger:"item",formatter:o=>this._tooltipFor(o,e)},...r.length?{legend:{show:!0,type:"custom",data:r}}:{}}}_standingOptions(e){return{xAxis:{type:"category",data:[V(this._period,e)]},yAxis:{type:"value",name:Y(e),nameGap:2,nameTextStyle:{align:"left"},axisLabel:{formatter:r=>K(r,e),hideOverlap:!0}},tooltip:{trigger:"item",formatter:r=>this._tooltipFor(r,e)},legend:{show:!0,type:"custom",data:[...this._ranked().map(r=>({id:`${r.key}:paid`,secondaryIds:[`${r.key}:saved`,...r.before?[`${r.key}:before`]:[]],name:r.name,itemStyle:{color:this._colourFor(r)}})),...this._earlierKey()]}}}},Ne=class extends m{_extraSchema(){return[{name:"layout",selector:{select:{mode:"dropdown",options:Uo}}}]}},ls=()=>{_(or,Ne),f(rr,Ie,{name:"Home Energy Advisor: Device costs (chart)",description:"What each device cost over the selected period, dearest first."})};ls();var ds=`${ie}
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
  /* A device that sits inside another one, indented under the row above it.
     Added to the verdict band's own padding rather than replacing it, so the
     band stays where it is on every row and only the name moves (HEA-153). */
  tbody th.inside { padding-left: 30px; }
  /* A circuit's own meter, which contains the rows under it. Weighted like the
     totals line it behaves like, so a reader can see it is a subtotal and not
     another device competing with its own children. */
  tbody tr.subtotal th, tbody tr.subtotal td { font-weight: 500; }
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
`,sr=(t,e,r)=>{let o=t==="costSavings"?T(r):H(e,r);return o?` class="${o}"`:""},nr=t=>t?` style="box-shadow: inset ${us} 0 0 ${t.edge}"`:"",us="4px",D=class extends F{static columns=[];static sorts={};static defaultSort="";static cardStyle=ds;setConfig(e){let{sorts:r}=this.constructor;if(e.sort_by!==void 0&&!(e.sort_by in r))throw new Error(`\`sort_by\` must be one of: ${Object.keys(r).join(", ")}`);super.setConfig(e)}getCardSize(){return 3+Math.ceil((this._result?.devices.length??3)/2)}_columns(){return this.constructor.columns}_body(e){let r=this._columns(),o=this._verdictScale();return`
      <div class="scroll">
        <table>
          <thead><tr>${r.map(s=>this._heading(s,e)).join("")}</tr></thead>
          <tbody>${this._ranked().map(({device:s,depth:a})=>this._row(s,e,o,a)).join("")}</tbody>
          <tfoot>${this._total(e,o)}</tfoot>
        </table>
      </div>`}_verdictScale(){if(this._columns().some(e=>e.carriesVerdict))return me(this._result?.devices??[],{dark:ae(this)})}_heading({label:e},r){let o=this._labels;if(typeof e!="function")return`<th>${ce(e)}${o[e]}</th>`;let{text:s,unit:a}=e(r,o);return`<th>${s} <span class="unit">${g(a)}</span></th>`}_rank(e){let{sorts:r,defaultSort:o}=this.constructor,{field:s}=r[this._config?.sort_by??o];return[...e].sort((a,n)=>n[s]-a[s]||a.name.localeCompare(n.name))}_ranked(){return Wt(this._result?.devices??[],this._labels,e=>this._rank(e))}_row(e,r,o,s){return`<tr${e.subtotal?' class="subtotal"':""}>${this._columns().map(n=>this._cell(n,e,r,o?.(e),s)).join("")}</tr>`}_cell({field:e,derive:r,format:o,tone:s,carriesVerdict:a,reveal:n},i,c,l,u){if(!o)return`<th scope="row"${u?' class="inside"':""}${nr(l)}>${g(i.name)}</th>`;let p=r?r(i):i[e],x=a?this._verdictOn(l,c):"",ee=this._revealed(o(p,c),n?.(i,c,this._labels));return`<td${sr(e,s,p)}${x}>${ee}</td>`}_revealed(e,r){return r?`<span class="reveal" tabindex="0" aria-label="${g(r.label)}">${e}<span class="revealed" aria-hidden="true">${g(r.text)}</span></span>`:e}_total(e,r){let o=this._sumOfShown(),s=r?.(o);return`<tr>${this._columns().map(({field:n,derive:i,format:c,tone:l,carriesVerdict:u})=>{if(!c)return`<th scope="row"${nr(s)}>${this._labels.total}</th>`;let p=i?i(o):o[n],x=u?this._verdictOn(s,e):"";return`<td${sr(n,l,p)}${x}>${c(p,e)}</td>`}).join("")}</tr>`}_verdictOn(e,r){if(!e)return"";let o=he(e.rate,this._labels,r);return` style="color: ${e.text}" title="${g(o)}"`}_sumOfShown(){let e=[...new Set(this._columns().flatMap(({field:n,fields:i,derive:c,format:l})=>l?c?i??[]:n?[n]:[]:[]))],r=ue(this._result?.devices??[],this._labels),o=Object.fromEntries(this._columns().flatMap(({fields:n,field:i,readField:c})=>c?(n??[i]).map(l=>[l,c]):[])),s=n=>r.reduce((i,c)=>{for(let l of e){let u=n(c);i[l]+=o[l]?o[l](u,l):u[l]}return i},Object.fromEntries(e.map(i=>[i,0]))),a=s(n=>n);return r.length>0&&r.every(n=>n.before)&&(a.before=s(n=>n.before)),a}},pe=(t,e)=>[{name:"sort_by",selector:{select:{mode:"dropdown",options:Object.entries(t).map(([r,{label:o}])=>({value:r,label:e[o]}))}}}];var ir="hea-devices-card",cr=`${ir}-editor`,hs=({actualCost:t,energyUsed:e})=>e>0?t/e:void 0,Me=t=>Object.values(C).every(e=>e in(t.statistics??{})),L={fields:["costFloor","costCeiling"],derive:({costFloor:t,costCeiling:e})=>[t,e],label:"range_column",format:I,readField:(t,e)=>Number.isFinite(t[e])?t[e]:t.actualCost},lr={fields:["actualCost"],derive:({actualCost:t,before:e})=>e&&Number.isFinite(t)&&Number.isFinite(e.actualCost)?t-e.actualCost:void 0,label:"change",format:G,tone:"actualCost"},fe={field:"actualCost",label:"paid",format:d,reveal:(t,e)=>{if(!Me(t)||!L.fields.every(o=>Number.isFinite(t[o])))return null;let r=I(L.derive(t),e);return{text:r,label:`${d(t.actualCost,e)} (${r})`}}},ms={fields:["actualCost","forgoneExport"],derive:t=>t.actualCost+(t.forgoneExport??0),label:"paid_with_forgone",format:d,reveal:(t,e,r)=>{let o=t.forgoneExport??0;if(!Number.isFinite(o)||o<=0)return fe.reveal(t,e);let s={paid:d(t.actualCost,e),forgone:d(o,e)},n=Me(t)&&L.fields.every(c=>Number.isFinite(t[c]))?b(r.paid_breakdown,{...s,range:I(L.derive(t),e)}):b(r.paid_breakdown_unranged,s),i=d(t.actualCost+o,e);return{text:n,label:`${r.paid_with_forgone} ${i}: ${n}`}}},dr={field:"forgoneExport",label:"forgone_column",format:d},ar=[{field:"name",label:"device"},{field:"energyUsed",label:"energy",format:k},fe,lr,L,dr,{field:"costAtGridPrice",label:"would_have_paid",format:d,carriesVerdict:!0},{field:"costSavings",label:"saved",format:d},{derive:hs,label:(t,e)=>({text:e.rate,unit:dt(t)}),format:ut}],ur={actual_cost:{field:"actualCost",label:"paid"},cost_at_grid_price:{field:"costAtGridPrice",label:"would_have_paid"},cost_savings:{field:"costSavings",label:"saved"},energy_used:{field:"energyUsed",label:"energy_used"}},De=class extends D{static titleKey="title_devices";static columns=ar;static sorts=ur;static defaultSort="actual_cost";static cardStyle=`${D.cardStyle}
    .disclosure {
      margin-top: var(--hea-space-m);
      color: var(--secondary-text-color);
      font-size: 0.8em;
    }
  `;static getConfigElement(){return document.createElement(cr)}_columns(){let e=this._rangeAsColumn(),r=this._withForgone(),o=r?ms:fe,s=new Set;return e||s.add(L),e&&r||s.add(dr),this._hasComparison()||s.add(lr),ar.filter(a=>!s.has(a)).map(a=>a!==fe?a:e?{...o,reveal:void 0}:o)}_rangeAsColumn(){return this._config?.range==="column"&&this._hasEveryBound()}_withForgone(){return this._config?.forgone!=="exclude"&&this._hasForgone()}_hasComparison(){return(this._result?.devices??[]).some(e=>e.before)}_hasForgone(){return(this._result?.devices??[]).some(e=>(e.forgoneExport??0)>0)}_hasEveryBound(){let e=(this._result?.devices??[]).filter(Me);return e.length>0&&e.every(r=>L.fields.every(o=>Number.isFinite(r[o])))}_body(e){return`${super._body(e)}${this._disclosure(e)}`}_disclosure(e){let r=this._labels;if(this._hasEveryBound())return`<div class="disclosure">${this._rangeNote()}</div>`;let o=this._result?.wholeHome;if(!o)return"";let s=I([o.costFloor,o.costCeiling],e);return`<div class="disclosure">
      ${b(r.range_whole_home,{range:s})}
    </div>`}_rangeNote(){let e=this._labels;return this._rangeAsColumn()?this._withForgone()?`${e.range_note} ${e.range_note_not_cost_of_use}`:e.range_note:this._withForgone()?e.range_note_cost_of_use:e.range_note_rollover}},Le=class extends m{_extraSchema(){let e=v(this._hass);return[...pe(ur,e),{name:"forgone",selector:{select:{mode:"dropdown",options:[{value:"include",label:e.editor_forgone_include},{value:"exclude",label:e.editor_forgone_exclude}]}}},{name:"range",selector:{select:{mode:"dropdown",options:[{value:"rollover",label:e.editor_range_rollover},{value:"column",label:e.editor_range_column}]}}}]}},ps=()=>{_(cr,Le),f(ir,De,{name:"Home Energy Advisor: Devices",description:"Every tracked device over the selected period, ordered by what it cost."})};ps();var Q="household",X=Object.freeze({source:0,household:1,floor:2,area:3,device:4}),hr=Object.freeze({cost:{field:"actualCost",sources:null},energy:{field:"energyUsed",sources:[{id:"grid",field:"energyFromGrid",variable:"--energy-grid-consumption-color",fallback:"#488fc2"},{id:"generation",field:"energyFromGeneration",variable:"--energy-solar-color",fallback:"#ff9800"},{id:"battery",field:"energyFromBattery",variable:"--energy-battery-out-color",fallback:"#4db6ac"}]}}),fs=t=>{let e=B(t);return r=>r.untracked?U.fallback:e.get(r.key)??E[0]},_s=({fallback:t})=>t,fr=(t,e,{metric:r="cost",colour:o=_s,deviceColour:s=fs(t)}={})=>{let{field:a,sources:n}=hr[r]??hr.cost,i=t.filter(h=>h[a]>0);if(i.length===0)return{nodes:[],links:[]};let c=new Map,l=new Map,u=[],p=[],x=0;i.forEach(h=>{let z=h[a];x+=z;let Ve=h.floorId?mr(c,h.floorId,h.floorName):null,_e=h.areaId?mr(l,h.areaId,h.areaName):null;Ve&&(Ve.value+=z),_e&&(_e.value+=z,_e.floorId??=h.floorId??null);let qe=`device_${h.key}`;u.push({id:qe,label:h.name,value:z,index:X.device,color:s(h),...bs(h)}),p.push({source:ys(h),target:qe,value:z})});let ee=gs(n,i,e,o);return{nodes:[...ee,{id:Q,label:e.household,value:x,index:X.household},...pr(c,"floor_",X.floor),...pr(l,"area_",X.area),...u],links:[...ee.map(h=>({source:h.id,target:Q,value:h.value})),...vs(c,l),...p]}},gs=(t,e,r,o)=>(t??[]).map(s=>({id:`source_${s.id}`,label:r[s.id],value:e.reduce((a,n)=>a+(n[s.field]??0),0),index:X.source,color:o(s)})).filter(s=>s.value>0),mr=(t,e,r)=>(t.has(e)||t.set(e,{id:e,name:r||e,value:0}),t.get(e)),ys=t=>t.areaId?`area_${t.areaId}`:t.floorId?`floor_${t.floorId}`:Q,bs=t=>{let e=t.statistics?.actual_cost;return e?{entityId:e}:{}},pr=(t,e,r)=>[...t.values()].map(o=>({id:`${e}${o.id}`,label:o.name,value:o.value,index:r})),vs=(t,e)=>[...[...t.values()].map(r=>({source:Q,target:`floor_${r.id}`,value:r.value})),...[...e.values()].map(r=>({source:r.floorId?`floor_${r.floorId}`:Q,target:`area_${r.id}`,value:r.value}))];var gr="hea-distribution-card",yr=`${gr}-editor`,J={cost:{titleKey:"title_distribution",emptyKey:"no_cost_in_period",format:d},energy:{titleKey:"title_distribution_energy",emptyKey:"no_energy_in_period",format:k}},_r="(max-width: 767px)",xs="400px",ws=88,Es=240,ks=["auto","horizontal","vertical"],Ge=class extends w{static titleKey="title_distribution";static chartTag="ha-sankey-chart";static bearingCard={type:"energy-sankey"};static narrowQuery=_r;static cardStyle=`
    ha-sankey-chart { display: block; min-height: 240px; }
  `;static getConfigElement(){return document.createElement(yr)}_isEmpty(){return this._layout().nodes.length===0}_verticalHeight({nodes:e}){let r=new Set(e.map(o=>o.index)).size;return`${Math.max(Es,r*ws)}px`}_metric(){return J[this._config?.metric]?this._config.metric:"cost"}_titleKey(){return J[this._metric()].titleKey}_emptyKey(){return J[this._metric()].emptyKey}_layout(){let e=B(y(this._hass));return fr(this._result?.devices??[],this._labels,{metric:this._metric(),colour:r=>this._colour(r),deviceColour:r=>r.untracked?this._colour(U):e.get(r.key)??E[0]})}_chartMarkup(){return"<ha-sankey-chart></ha-sankey-chart>"}_draw(e){e.data=this._layout(),e.vertical=this._isVertical(),e.style.height=this._isVertical()?this._verticalHeight(e.data):xs;let r=this._chartLocale(),{format:o}=J[this._metric()];e.valueFormatter=s=>o(s,r),this.toggleAttribute("data-vertical",e.vertical)}_isVertical(){let e=this._config?.layout;return e==="vertical"?!0:e==="horizontal"?!1:!!globalThis.matchMedia?.(_r)?.matches}},He=class extends m{_extraSchema(){return[{name:"metric",selector:{select:{mode:"dropdown",options:Object.keys(J)}}},{name:"layout",selector:{select:{mode:"dropdown",options:ks}}}]}},Ss=()=>{_(yr,He),f(gr,Ge,{name:"Home Energy Advisor: Cost distribution",description:"Where the period's cost went, by floor, room and device."})};Ss();var br="hea-filter-card",vr=`${br}-editor`,Ts=[{kind:"area",label:"filter_rooms",id:"areaId",name:"areaName"},{kind:"floor",label:"filter_floors",id:"floorId",name:"floorName"}],M=({kind:t,id:e})=>`${t}:${e??""}`,As=t=>{let[e,r]=[t.slice(0,t.indexOf(":")),t.slice(t.indexOf(":")+1)];return{kind:e,id:r===""?null:r}},Pe=class extends HTMLElement{constructor(){super(),this.attachShadow({mode:"open"})}setConfig(e){this._config=e,this._render()}set hass(e){this._hass=e,A(e).then(()=>this._renderIfChanged()),this._renderIfChanged()}getCardSize(){return 1}static getConfigElement(){return document.createElement(vr)}connectedCallback(){this._render(),this._unfilter??=se(this._config?.collection_key,()=>this._renderIfChanged())}_signature(){return JSON.stringify([this._allDevices().map(e=>[e.key,e.name,e.areaId,e.areaName,e.floorId,e.floorName,e.labels]),M(W(this._config?.collection_key)),this._labels.filter_rooms])}_renderIfChanged(){this._signature()!==this._drawn&&this._render()}disconnectedCallback(){this._unfilter?.(),this._unfilter=null}get _labels(){return v(this._hass)}_devices(){return y(this._hass).filter(e=>!e.untracked)}_allDevices(){return y(this._hass)}_optionsFor({kind:e,id:r,name:o},s){let a=new Map,n=!1;for(let c of s)c[r]?a.set(c[r],c[o]??c[r]):n=!0;let i=[...a.entries()].map(([c,l])=>({value:M({kind:e,id:c}),text:l})).sort((c,l)=>c.text.localeCompare(l.text));return n&&i.push({value:M({kind:e,id:null}),text:this._labels.filter_unfiled}),i}_labelOptions(e){let r=tt(this._hass);return[...new Set(e.flatMap(s=>s.labels??[]))].map(s=>({value:M({kind:"label",id:s}),text:r[s]??s})).sort((s,a)=>s.text.localeCompare(a.text))}_deviceOptions(){return this._allDevices().map(e=>({value:M({kind:"device",id:e.key}),text:e.name})).sort((e,r)=>e.text.localeCompare(r.text))}_groups(){let e=this._devices(),r=Ts.map(s=>({label:this._labels[s.label],options:this._optionsFor(s,e)})),o=this._labelOptions(e);return o.length&&r.push({label:this._labels.filter_labels,options:o}),r.push({label:this._labels.filter_devices,options:this._deviceOptions()}),r.filter(s=>s.options.length>0)}_render(){let e=this._labels,r=this._devices();this._drawn=this._signature();let o=r.length?this._control(e):`<p class="message">${e.no_devices}</p>`;this.shadowRoot.innerHTML=`
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
    `;let s=this.shadowRoot.querySelector("select");s&&(s.value=M(W(this._config?.collection_key)),s.addEventListener("change",()=>st(this._config?.collection_key,As(s.value))))}_control(e){let r=this._groups().map(o=>`<optgroup label="${g(o.label)}">${o.options.map(s=>`<option value="${g(s.value)}">${g(s.text)}</option>`).join("")}</optgroup>`).join("");return`<div class="body">
      <span class="label">${e.title_filter}</span>
      <select>
        <option value="${M({kind:"all",id:null})}">${g(e.filter_everything)}</option>
        ${r}
      </select>
    </div>`}},je=class extends m{},Cs=()=>{_(vr,je),f(br,Pe,{name:"Home Energy Advisor: Filter",description:"Narrow every Home Energy Advisor card on the page to a room, a floor, a label or one device."})};Cs();var wr="hea-self-sufficiency-card",Er=`${wr}-editor`,xr=["energyUsed","energyFromGrid","energyFromGeneration","energyFromBattery"],Os={maximumFractionDigits:0},Fs=.005,Ue=class extends w{static titleKey="title_self_sufficiency";static chartTag="ha-gauge";static bearingCard={type:"energy-self-sufficiency-gauge"};static emptyKey="no_energy_in_period";static cardStyle=`
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
      <div class="headline">${this._labels.from_generation}</div>`}_breakdown(e){let{battery:r,grid:o,unaccounted:s}=this._shares();return`<div class="shares">${[{label:"from_battery",value:r},{label:"from_grid",value:o},{label:"unaccounted",value:s}].filter(({label:n,value:i})=>n!=="unaccounted"||i>Fs).map(({label:n,value:i})=>`
        <div class="share">
          <span class="label">${this._labels[n]}</span>
          <span class="value" data-share="${n}">${P(i,e)}</span>
        </div>`).join("")}</div>
      <div class="note">${this._labels.self_sufficiency_note}</div>`}_draw(e){e.min=0,e.max=100,e.value=this._shares().generation*100,e.label="%",e.formatOptions=Os,e.locale=this._hass?.locale}},Be=class extends m{},$s=()=>{_(Er,Be),f(wr,Ue,{name:"Home Energy Advisor: Self-sufficiency",description:"What share of the selected period's energy came from the household's own generation."})};$s();var kr="hea-sources-card",Sr=`${kr}-editor`,Rs=({energyFromGrid:t,energyUsed:e})=>e>0&&t>=0&&t<=e?t/e:void 0,Is=[{field:"name",label:"device"},{field:"energyUsed",label:"energy",format:k},{field:"energyFromGrid",label:"grid",format:k},{field:"energyFromGeneration",label:"generation",format:k},{field:"energyFromBattery",label:"battery",format:k},{derive:Rs,label:"from_grid",format:P}],Tr={energy_used:{field:"energyUsed",label:"energy_used"},energy_from_grid:{field:"energyFromGrid",label:"from_grid"},energy_from_generation:{field:"energyFromGeneration",label:"from_generation"},energy_from_battery:{field:"energyFromBattery",label:"from_battery"}},ze=class extends D{static titleKey="title_sources";static columns=Is;static sorts=Tr;static defaultSort="energy_used";static getConfigElement(){return document.createElement(Sr)}},We=class extends m{_extraSchema(){return pe(Tr,v(this._hass))}},Ns=()=>{_(Sr,We),f(kr,ze,{name:"Home Energy Advisor: Energy sources",description:"Grid, generation and battery behind each device's energy over the period."})};Ns();var Ar="hea-totals-card",Cr=`${Ar}-editor`,Ds=[{key:"actualCost",label:"paid"},{key:"costAtGridPrice",label:"would_have_paid"},{key:"costSavings",label:"saved"}],Ke=class extends F{static titleKey="title_totals";static cardStyle=`${ie}
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
  `;static getConfigElement(){return document.createElement(Cr)}getCardSize(){return 3}_body(e){let r=this._result?.totals;return`<div class="figures">${Ds.map(({key:s,label:a})=>{let n=r?.[s],i=s==="costSavings"?T(n):"",c=i?` ${i}`:"";return`
        <div class="figure">
          <span class="label">${ce(a)}${this._labels[a]}</span>
          <span class="value${c}" data-figure="${s}">${d(n,e)}</span>
          ${this._comparedTo(s,n,e)}
        </div>`}).join("")}</div>`}_comparedTo(e,r,o){let s=this._result?.totals?.before?.[e];if(!Number.isFinite(s)||!Number.isFinite(r))return"";let a=H(e,r-s);return`<span class="${a?`compare ${a}`:"compare"}" data-compare="${e}">${b(this._labels.compared,{change:G(r-s,o),before:d(s,o)})}</span>`}},Ye=class extends m{},Ls=()=>{_(Cr,Ye),f(Ar,Ke,{name:"Home Energy Advisor: Totals",description:"What the selected period cost, what it would have cost at grid price, and the difference."})};Ls();
