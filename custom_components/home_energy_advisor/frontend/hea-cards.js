var Or=[4,4,0,0],Cr=[0,0,4,4],qe=t=>t!==null&&typeof t=="object"&&!Array.isArray(t),Fr=t=>{let e=qe(t)?t.value:t;return Array.isArray(e)?e[1]:e},ge=(t,e)=>{let r=qe(t)?{...t}:{value:t};return{...r,itemStyle:{...r.itemStyle,...e}}},te=t=>{let e=Math.max(...t.map(({data:o})=>o.length),0),r=t.map(({data:o})=>[...o]);for(let o of $r(t))for(let s=0;s<e;s++)Rr(r,s,o);return t.map((o,s)=>({...o,data:r[s]}))},$r=t=>{let e=new Map;return t.forEach((r,o)=>{let s=r.stack??Symbol(o),a=e.get(s);a?a.push(o):e.set(s,[o])}),[...e.values()]},Rr=(t,e,r)=>{let o=!1,s=!1;for(let a=r.length-1;a>=0;a--){let n=r[a],i=t[n][e];if(i===void 0)continue;let c=Fr(i);c?c>0&&!o?(t[n][e]=ge(i,{borderRadius:Or}),o=!0):c<0&&!s&&(t[n][e]=ge(i,{borderRadius:Cr}),s=!0):t[n][e]=ge(i,{borderWidth:0})}};var Ze="_energy",ye="energy_";var Ir=(t,e)=>{let r=t||(e?`${ye}${e}`:"");return r?r.startsWith(ye)?`_${r}`:`_${ye}${r}`:Ze},Nr=(t,e)=>typeof t=="string"&&t.startsWith(Ze)&&e!==null&&typeof e=="object"&&typeof e.subscribe=="function"&&"start"in e,Dr=(t=new Date)=>{let e=new Date(t);return e.setDate(e.getDate()-30),e.setHours(0,0,0,0),{start:e,end:t,fallback:!0}},Lr=t=>{let e=t?.connection;if(!e)return{};let r={};for(let o of Object.keys(e)){let s;try{s=e[o]}catch{continue}Nr(o,s)&&(r[o]=s)}return r},Mr=(t,e)=>{let r=Lr(t),o=Ir(e,t?.panelUrl);if(r[o])return r[o];let[s]=Object.values(r);return s??null},Gr=t=>t?.startCompare&&t?.endCompare?{compare:{start:t.startCompare,end:t.endCompare,mode:t.compareMode}}:{},Xe=(t,e,r)=>{let o=null,s=null,a=0,n=t,i=l=>{if(o)return!0;let d=Mr(l,e);if(!d)return!1;let p=x=>r({start:d.start,end:d.end,fallback:!1,...Gr(x)});return o=d.subscribe(p),p(),!0},c=()=>{s=setTimeout(()=>{s=null,a+=1,!i(n)&&a<40&&c()},250)};return r(Dr()),i(t)||c(),{retry:l=>(l&&(n=l),i(n)),unsubscribe:()=>{s&&clearTimeout(s),s=null;try{typeof o=="function"&&o()}catch{}o=null}}};var re="sensor.home_energy_advisor_devices",Hr="home_energy_advisor",oe=t=>{if(t?.states?.[re])return re;let e=t?.entities;if(!e)return re;for(let[r,o]of Object.entries(e))if(o?.platform===Hr&&Array.isArray(t?.states?.[r]?.attributes?.devices))return r;return re},y=(t,e=void 0)=>{let r=t?.states?.[e??oe(t)]?.attributes?.devices;return Array.isArray(r)?r.filter(o=>o?.key).map(tt):[]},Qe=(t,e=void 0)=>{let r=t?.states?.[e??oe(t)]?.attributes?.whole_home;return r?.key?tt(r):null},Je=(t,e=void 0)=>{let r=t?.states?.[e??oe(t)]?.attributes?.settled_until;if(typeof r!="string")return null;let o=new Date(r);return Number.isNaN(o.getTime())?null:o},et=(t,e=void 0)=>{let r=t?.states?.[e??oe(t)]?.attributes?.labels;return r&&typeof r=="object"?r:{}},tt=t=>({key:t.key,name:t.name||t.key,deviceId:t.device_id??null,untracked:!!t.untracked,statistics:t.statistics??{},areaId:t.area_id??null,areaName:t.area_name??null,floorId:t.floor_id??null,floorName:t.floor_name??null,upstream:t.upstream??null,labels:Array.isArray(t.labels)?t.labels:[]});var rt=Object.freeze({kind:"all",id:null}),Pr={area:"areaId",floor:"floorId"},be=new Map,ve=t=>(be.has(t)||be.set(t,{filter:rt,listeners:new Set}),be.get(t)),z=t=>ve(t).filter,se=(t,e)=>{let{listeners:r}=ve(t);return r.add(e),()=>r.delete(e)},ot=(t,e)=>{let r=ve(t),o={kind:e?.kind??"all",id:e?.id??null};if(!(o.kind===r.filter.kind&&o.id===r.filter.id)){r.filter=o;for(let s of r.listeners)try{s(o)}catch(a){console.warn("home-energy-advisor: a card could not follow the filter",a)}}},st=(t,e)=>{let{kind:r,id:o}=e??rt;if(r==="all")return!0;if(r==="device")return t.key===o;if(t.untracked)return!1;if(r==="label")return(t.labels??[]).includes(o);let s=Pr[r];return s?(t[s]??null)===o:!0};var jr={day:"numeric",month:"short",year:"numeric"},ne=t=>({language:t?.locale?.language||void 0,currency:t?.config?.currency||void 0,timeFormat:t?.locale?.time_format||void 0,timeZone:t?.locale?.time_zone==="server"?t?.config?.time_zone:void 0}),Ur=({timeFormat:t,language:e})=>{if(t==="language"||t==="system"||!t){let r=t==="system"?void 0:e;return new Date("January 1, 2023 22:00:00").toLocaleString(r).includes("10")}return t==="12"},nt=(t,e)=>new Intl.DateTimeFormat(e.language,{hour:"numeric",minute:"2-digit",hourCycle:Ur(e)?"h12":"h23",timeZone:e.timeZone}).format(t),Br=(t,e)=>new Intl.DateTimeFormat(e.language,{weekday:"short",month:"short",day:"numeric",timeZone:e.timeZone}).format(t),zr={hour:3600*1e3},at=(t,e,r)=>{let o=zr[e];if(!o)return Br(t,r);let s=new Date(t.getTime()+o);return`${nt(t,r)} \u2013 ${nt(s,r)}`},h=(t,{language:e,currency:r})=>{if(typeof t!="number"||!Number.isFinite(t))return"-";let o=r?{style:"currency",currency:r}:{minimumFractionDigits:2,maximumFractionDigits:2};return new Intl.NumberFormat(e,o).format(t)},L=(t,{language:e,currency:r})=>{if(typeof t!="number"||!Number.isFinite(t))return"-";let o=r?{style:"currency",currency:r,signDisplay:"exceptZero"}:{minimumFractionDigits:2,maximumFractionDigits:2,signDisplay:"exceptZero"};return new Intl.NumberFormat(e,o).format(t)},Wr=new Set(["actualCost","costAtGridPrice","energyUsed"]),Kr=new Set(["costSavings"]),T=t=>typeof t!="number"||!Number.isFinite(t)||t===0?"":t>0?"gain":"loss",M=(t,e)=>typeof e!="number"||!Number.isFinite(e)||e===0?"":Wr.has(t)?e<0?"gain":"loss":Kr.has(t)?e>0?"gain":"loss":"",G=(t,e)=>{if(!Array.isArray(t))return"-";let[r,o]=t;if(![r,o].every(n=>Number.isFinite(n)))return"-";if(r===o)return h(r,e);let[s,a]=r<=o?[r,o]:[o,r];return`${h(s,e)} - ${h(a,e)}`},k=(t,{language:e})=>typeof t!="number"||!Number.isFinite(t)?"-":`${new Intl.NumberFormat(e,{maximumFractionDigits:1}).format(t)} kWh`,it={EUR:{symbol:"c",per:100},USD:{symbol:"\xA2",per:100},GBP:{symbol:"p",per:100}},W=(t,{language:e})=>typeof t!="number"||!Number.isFinite(t)?"-":new Intl.NumberFormat(e,{minimumFractionDigits:t===0?0:2,maximumFractionDigits:2}).format(t),K=({language:t,currency:e})=>e?ct(t,e):"",ct=(t,e)=>new Intl.NumberFormat(t,{style:"currency",currency:e}).formatToParts(0).find(r=>r.type==="currency")?.value??"",lt=({language:t,currency:e})=>{if(!e)return"/kWh";let r=it[e];return`${r?r.symbol:ct(t,e)}/kWh`},dt=(t,{language:e,currency:r})=>{if(typeof t!="number"||!Number.isFinite(t))return"-";let o=r?it[r]:void 0;return new Intl.NumberFormat(e,{minimumFractionDigits:o?1:0,maximumFractionDigits:o?2:3}).format(o?t*o.per:t)},H=(t,{language:e})=>typeof t!="number"||!Number.isFinite(t)?"-":new Intl.NumberFormat(e,{style:"percent",maximumFractionDigits:0}).format(t),g=t=>String(t).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#39;"),Y=(t,{language:e})=>t?new Intl.DateTimeFormat(e,jr).formatRange(t.start,t.end):"";var ut="common",mt="home_energy_advisor",ht=`component.${mt}.${ut}.card_`,we=Object.freeze({paid:"Paid",would_have_paid:"Would have paid",saved:"Saved",lost:"Lost",paid_with_forgone:"Cost of use",range_column:"Paid (min-max)",range_note:"Paid (min-max) is the widest range these readings allow, not a typical error: a meter that reports every 30-90 minutes leaves the exact moment of use unknown.",range_whole_home:"What you paid could honestly sit between {range} - the widest these readings allow, not a typical error.",range_device:"What you paid could be between {range}.",compared:"{change} vs {before}",compared_period:"{period} vs {compared}",saved_share:"{percent} of what you would have paid was saved.",lost_share:"{percent} more was paid than the grid would have cost.",change:"Change",compared_series:"Earlier period",device:"Device",energy:"Energy",rate:"Rate",total:"Total",grid:"Grid",generation:"Generation",battery:"Battery",from_grid:"From the grid",from_generation:"From generation",from_battery:"From the battery",energy_used:"Energy used",unaccounted:"Unaccounted",self_sufficiency_note:"Battery energy is counted on its own: it was charged from generation or from the grid, and these readings cannot say which.",household:"Household",title_totals:"Cost summary",title_devices:"Cost by device",title_device_costs:"What each device cost",title_cost_over_time:"Cost over time",title_sources:"Where the energy came from",title_self_sufficiency:"Self-sufficiency",title_distribution:"Where the cost went",title_distribution_energy:"Where the energy went",no_devices:"No devices are being tracked yet.",no_devices_in_filter:"No tracked device matches what the page is showing.",title_filter:"Show",filter_everything:"Everything",filter_rooms:"Rooms",filter_floors:"Floors",filter_labels:"Labels",filter_devices:"Devices",filter_unfiled:"Not in one",device_untracked:"Untracked",hourly_shape_estimate:"One device's hourly shape is an estimate: each meter reading is spread across the hours it spanned, so cost may not land in the hour the energy was used.",still_accruing:"The last interval is still being counted, so its bar will grow. Figures are complete about twenty minutes behind the clock, which is how long meters are given to report.",statistics_failed:"Statistics could not be loaded.",no_picker:"Add an Energy date picker card to choose the range.",chart_not_loaded:"Home Assistant's chart component is not loaded. Adding any energy or statistics card to this dashboard will load it.",no_cost_in_period:"No cost recorded in this period.",no_energy_in_period:"No energy recorded in this period.",editor_title:"Title",editor_collection_key:"Energy period (collection key)",editor_devices:"Devices (all, if none are chosen)",editor_sort_by:"Order by",editor_layout:"Layout",editor_metric:"Measure by",editor_forgone:"Count what your own generation could have earned",editor_forgone_include:"Include it in the cost",editor_forgone_exclude:"Show only what you paid",editor_range:"Show the cost range as",editor_range_rollover:"A rollover on Paid",editor_range_column:"Its own column"}),xe=new Map,pt=new Map,ft=t=>t?.locale?.language||t?.language||"en",A=t=>{let e=ft(t);return xe.has(e)||xe.set(e,Yr(t,e).then(r=>(pt.set(e,r),r))),xe.get(e)},Yr=async(t,e)=>{try{let{resources:r}=await t.callWS({type:"frontend/get_translations",language:e,category:ut,integration:[mt]});return Object.freeze({...we,...Vr(r)})}catch(r){return console.warn("home-energy-advisor: falling back to English labels",r),we}},b=t=>pt.get(ft(t))??we,Vr=t=>Object.fromEntries(Object.entries(t??{}).filter(([e,r])=>e.startsWith(ht)&&r).map(([e,r])=>[e.slice(ht.length),r])),v=(t,e)=>Object.entries(e).reduce((r,[o,s])=>r.replaceAll(`{${o}}`,s),t);var P=Object.freeze({energyUsed:"energy_used",actualCost:"actual_cost",costAtGridPrice:"cost_at_grid_price",energyFromGrid:"energy_from_grid",energyFromGeneration:"energy_from_generation",energyFromBattery:"energy_from_battery",forgoneExport:"forgone_export"}),O=Object.freeze({costFloor:"lowest_possible_cost",costCeiling:"highest_possible_cost"}),Ee=()=>Object.fromEntries(Object.keys(P).map(t=>[t,0])),yt=1440*60*1e3,bt={hour:3600*1e3,day:yt},qr=2,V=(t,e)=>t?.statistics?.[e],Zr=(t,e)=>{let r=t.flatMap(o=>[...Object.values(P),...Object.values(O)].map(s=>V(o,s)).filter(Boolean));return!e?.statistics||t.length===0?r:[...r,...Object.values(O).map(o=>V(e,o)).filter(Boolean)]},vt=(t,e)=>{if(!e)return t;let r=new Map(e.devices.map(o=>[o.key,o]));return{...t,totals:{...t.totals,before:e.totals},devices:t.devices.map(o=>({...o,before:r.get(o.key)})),seriesBefore:Xr(e.series,t.period,e.period)}},Xr=(t,e,r)=>{if(!t?.length)return;let o=e.start.getTime()-r.start.getTime();return t.map(s=>({...s,start:new Date(s.start.getTime()+o),actualStart:s.start}))},C=({start:t,end:e})=>e-t>qr*yt?"day":"hour",_t=(t,e,r)=>{if(e!=="day")return new Date(t.getTime()+r*bt.hour);let o=new Date(t);return o.setDate(o.getDate()+r),o},xt=(t,e)=>{if(!t.length||!e)return t;let r=C(e),o=new Map(t.map(n=>[n.start.getTime(),n])),s=t[0].start,a=[];for(let n=0;;n--){let i=_t(s,r,n);if(i.getTime()<e.start.getTime())break;a.push(o.get(i.getTime())??gt(i))}a.reverse();for(let n=1;;n++){let i=_t(s,r,n);if(i.getTime()>=e.end.getTime())break;a.push(o.get(i.getTime())??gt(i))}return a},gt=t=>({...Ee(),start:t,costSavings:0,accruing:!1}),ke=async(t,e,r,o,s=null)=>{let a=Zr(e,o),n=a.length?await t.callWS({type:"recorder/statistics_during_period",start_time:r.start.toISOString(),end_time:r.end.toISOString(),statistic_ids:a,period:C(r),types:["change"]}):{},i=e.map(c=>Jr(c,n,r));return{period:r,devices:i,totals:eo(i),wholeHome:wt(o,n,r),series:Qr(e,n,r,s)}},wt=(t,e,r)=>{if(!t)return;let o={};for(let[s,a]of Object.entries(O)){let n=e?.[V(t,a)];if(!Array.isArray(n))return;o[s]=kt(n,r)}return o},Qr=(t,e,r,o)=>{let s=new Map;for(let n of t)for(let[i,c]of Object.entries(P)){let l=e?.[V(n,c)];for(let d of Et(l,r)){let p=s.get(d.start)??Ee();p[i]+=d.change,s.set(d.start,p)}}let a=bt[C(r)]??0;return[...s.entries()].sort(([n],[i])=>n-i).map(([n,i])=>({...i,start:new Date(n),costSavings:i.costAtGridPrice-i.actualCost,accruing:o?n+a>o.getTime():!1}))},Jr=(t,e,r)=>{let o=Object.fromEntries(Object.entries(P).map(([s,a])=>[s,kt(e?.[V(t,a)],r)]));return{...t,...o,...wt(t,e,r),costSavings:o.costAtGridPrice-o.actualCost}},Et=(t,{start:e,end:r})=>{if(!Array.isArray(t))return[];let o=[];for(let s of t){let a=new Date(s.start).getTime();a<e.getTime()||a>=r.getTime()||typeof s.change=="number"&&o.push({start:a,change:s.change})}return o},kt=(t,e)=>Et(t,e).reduce((r,o)=>r+o.change,0),eo=t=>({...t.reduce((r,o)=>{for(let s of Object.keys(r))r[s]+=o[s];return r},{...Ee(),costSavings:0}),...to(t)}),to=t=>{let e=Object.keys(O);return!t.length||!t.every(r=>e.every(o=>o in r))?{}:Object.fromEntries(e.map(r=>[r,t.reduce((o,s)=>o+s[r],0)]))};var ro=`
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
`,oo=`
  .loss { color: var(--error-color, #db4437); }
  .gain { color: var(--success-color, #4caf50); }
`,F=class extends HTMLElement{static cardStyle="";static titleKey="";_titleKey(){return this.constructor.titleKey}get _labels(){return b(this._hass)}constructor(){super(),this.attachShadow({mode:"open"}),this._state="loading",this._request=0}setConfig(e){if(e.devices!==void 0&&!Array.isArray(e.devices))throw new Error("`devices` must be a list of device keys");this._config=e,this._render()}set hass(e){this._hass=e,this._subscription?this._subscription.retry(e):this._subscribe(),this._refetchIfDevicesChanged()}connectedCallback(){this._render(),this._hass&&!this._subscription&&this._subscribe()}disconnectedCallback(){this._subscription?.unsubscribe(),this._subscription=null,this._unfilter?.(),this._unfilter=null}_subscribe(){this._subscription=Xe(this._hass,this._config?.collection_key,e=>{this._period=e,this._scheduleFetch()}),this._unfilter=se(this._config?.collection_key,()=>this._scheduleFetch())}_scheduleFetch(){this._fetchPending||(this._fetchPending=!0,queueMicrotask(()=>{this._fetchPending=!1,this._fetch()}))}_refetchIfDevicesChanged(){let e=this._devices().map(r=>r.key).join(",");e!==this._deviceKeys&&(this._deviceKeys=e,this._period&&this._scheduleFetch())}_devices(){let e=y(this._hass),r=this._config?.devices,o=r?e.filter(a=>r.includes(a.key)):e,s=this._filter();return o.filter(a=>st(a,s))}_filter(){return z(this._config?.collection_key)}_isFiltered(){return!!this._config?.devices||this._filter().kind!=="all"}async _fetch(){if(!this._hass||!this._period)return;let e=this._devices(),r=++this._request;if(await A(this._hass),e.length===0){this._state="empty",this._render();return}let o=this._isFiltered()?void 0:Qe(this._hass);try{let s=Je(this._hass),[a,n]=await Promise.all([ke(this._hass,e,this._period,o,s),this._period.compare?ke(this._hass,e,this._period.compare,o):void 0]);if(r!==this._request)return;this._result=vt(a,n),this._state="ready"}catch(s){if(r!==this._request)return;this._state="error",console.error(`${this.localName}: could not load statistics`,s)}this._render()}_render(){let e=ne(this._hass);this.shadowRoot.innerHTML=`
      <style>${ro}${this.constructor.cardStyle}${oo}</style>
      <ha-card>
        <div class="body" data-state="${this._state}">${this._content(e)}</div>
      </ha-card>
    `;let r=this._config?.title??this._labels[this._titleKey()];r&&this._writeHeader(r,e),this._afterRender()}_writeHeader(e,r){let o=this.shadowRoot.querySelector("ha-card"),s=this._headerChip(r);if(s===void 0){o.setAttribute("header",e);return}o.insertAdjacentHTML("afterbegin",`<div class="card-header" style="display: flex; justify-content: space-between;
         align-items: center; gap: var(--hea-space-s); padding-bottom: 0;">
        <span class="title">${g(e)}</span>
        <span class="chip">${g(s)}</span>
      </div>`)}_headerChip(){}_afterRender(){}_content(e){return this._state==="empty"?`<p class="message">${this._labels.no_devices}</p>`:this._state==="error"?`<p class="message">${this._labels.statistics_failed}</p>`:`${this._body(e)}${this._caption(e)}`}_caption(e){let r=this._period?.fallback?`<div class="hint">${this._labels.no_picker}</div>`:"";return`<div class="period">${this._periodLabel(e)}</div>${r}`}_periodLabel(e){let r=Y(this._period,e),o=this._period?.compare;return o?v(this._labels.compared_period,{period:r,compared:Y(o,e)}):r}},f=(t,e,{name:r,description:o})=>{customElements.get(t)||customElements.define(t,e),globalThis.customCards=globalThis.customCards??[],globalThis.customCards.some(s=>s.type===t)||globalThis.customCards.push({type:t,name:r,description:o})};var so={title:"editor_title",collection_key:"editor_collection_key",devices:"editor_devices",sort_by:"editor_sort_by",layout:"editor_layout",metric:"editor_metric",range:"editor_range"},m=class extends HTMLElement{constructor(){super(),this.attachShadow({mode:"open"})}setConfig(e){this._config=e,this._render()}set hass(e){this._hass=e,this._render(),A(e).then(()=>this._render())}_extraSchema(){return[]}_render(){if(!this._config)return;let e=this.shadowRoot.querySelector("ha-form");e||(e=document.createElement("ha-form"),e.computeLabel=r=>b(this._hass)[so[r.name]]??r.name,e.addEventListener("value-changed",r=>this._report(r.detail.value)),this.shadowRoot.append(e)),e.hass=this._hass,e.data=this._config,e.schema=this._schema()}_schema(){return[{name:"title",selector:{text:{}}},{name:"collection_key",selector:{text:{}}},{name:"devices",selector:{select:{multiple:!0,mode:"list",options:y(this._hass).map(e=>({value:e.key,label:e.name}))}}},...this._extraSchema()]}_report(e){this.dispatchEvent(new CustomEvent("config-changed",{detail:{config:no({...this._config,...e})},bubbles:!0,composed:!0}))}},no=t=>Object.fromEntries(Object.entries(t).filter(([,e])=>e!==""&&e!==void 0&&e!==null&&!(Array.isArray(e)&&e.length===0))),_=(t,e)=>{customElements.get(t)||customElements.define(t,e)};var w=class extends F{static chartTag="ha-chart-base";static bearingCard={type:"statistics-graph",entities:[]};static emptyKey="no_cost_in_period";static chartHeight="clamp(320px, 40vw, 480px)";static cardStyle=`
    ha-chart-base { display: block; --chart-max-height: none; }
  `;constructor(){super(),this._chartReady=!!customElements.get(this.constructor.chartTag)}getCardSize(){return 6}static narrowQuery="";connectedCallback(){super.connectedCallback(),this._chartReady||this._loadChartComponent(),this._watchScreen()}disconnectedCallback(){super.disconnectedCallback(),this._screen?.removeEventListener?.("change",this._onScreenChange),this._screen=null}_watchScreen(){let{narrowQuery:e}=this.constructor;!e||this._screen||(this._screen=globalThis.matchMedia?.(e),this._onScreenChange??=()=>this._render(),this._screen?.addEventListener?.("change",this._onScreenChange))}async _loadChartComponent(){let{chartTag:e,bearingCard:r}=this.constructor;customElements.whenDefined(e).then(()=>{this._chartReady=!0,this._render()});try{await(await globalThis.loadCardHelpers?.())?.createCardElement(r)}catch(o){console.warn(`${e}: could not be loaded`,o)}}_isEmpty(){return(this._result?.series??[]).length===0}_body(){return this._chartReady?this._isEmpty()?`<p class="message">${this._labels[this._emptyKey()]}</p>`:this._chartMarkup():`<p class="message">${this._labels.chart_not_loaded}</p>`}_emptyKey(){return this.constructor.emptyKey}_chartMarkup(){return'<ha-chart-base chart-type="bar"></ha-chart-base>'}_afterRender(){let e=this.shadowRoot.querySelector(this.constructor.chartTag);e&&(e.hass=this._hass,this._draw(e))}_chartHeight(){return this.constructor.chartHeight}_draw(e){e.height=this._chartHeight(),e.data=this._series(),e.options=this._options(this._chartLocale())}_chartLocale(){return ne(this._hass)}_colour({variable:e,fallback:r}){return getComputedStyle(this).getPropertyValue(e).trim()||r}};var ao=/^#([\da-f]{3}|[\da-f]{6})$/i,io=/^rgba?\(([^)]+)\)$/i,Se=t=>{let e=ao.exec(String(t).trim());if(e){let s=e[1];return(s.length===3?[...s].map(n=>n+n):[0,2,4].map(n=>s.slice(n,n+2))).map(n=>Number.parseInt(n,16))}let r=io.exec(String(t).trim());if(!r)return;let o=r[1].split(/[\s,/]+/).filter(Boolean).slice(0,3).map(Number);return o.length===3&&o.every(Number.isFinite)?o:void 0},S=(t,e)=>{let r=Se(String(t).trim());return r?`rgba(${r.join(", ")}, ${e})`:t},co=([t,e,r])=>(.2126*t+.7152*e+.0722*r)/255,ae=t=>{let e=Se(lo(t));return e?co(e)>.5:!1},lo=t=>{let e=[t,t?.ownerDocument?.documentElement].filter(Boolean);for(let r of e){let o=getComputedStyle(r),s=o.getPropertyValue("--primary-text-color").trim()||o.color;if(Se(s))return s}return""};var St=Object.freeze({variable:"--primary-color",fallback:"#03a9f4"}),Tt=Object.freeze({variable:"--success-color",fallback:"#4caf50"}),ho=Object.freeze({paid:"paid",would_have_paid:"would-have-paid",saved:"saved"}),ie=`
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
`,ce=t=>{let e=typeof t=="string"?ho[t]:void 0;return e?`<span class="swatch ${e}" aria-hidden="true"></span>`:""};var $=(t,e,r,{bold:o=!1}={})=>{let s=document.createElement("div");s.style.display="flex",s.style.justifyContent="space-between",s.style.gap="16px",o&&(s.style.fontWeight="bold");let a=document.createElement("span");a.textContent=t;let n=document.createElement("span");return n.textContent=e,n.style.fontVariantNumeric="tabular-nums",r&&(n.style.color=r),s.append(a,n),s},uo=t=>{let e=document.createElement("span");return e.style.display="inline-block",e.style.width="10px",e.style.height="10px",e.style.borderRadius="10px",e.style.marginInlineEnd="4px",e.style.verticalAlign="middle",e.style.backgroundColor=t,e},At=(t,e,r,o)=>{let s=$(e,r,o);return s.firstChild.prepend(uo(t)),s},le=t=>{let e=document.createElement("div");return e.textContent=t,e.style.fontWeight="bold",e.style.textAlign="center",e.style.marginBottom="4px",e},Ot=t=>{let e=document.createElement("div");return e.textContent=t,e.style.marginTop="4px",e.style.maxWidth="260px",e.style.whiteSpace="normal",e.style.opacity="0.7",e};var Rt="hea-cost-over-time-card",It=`${Rt}-editor`,mo={hour:3600*1e3,day:1440*60*1e3},po=50,fo=.5,_o=(t,e)=>{if(!t.length||!e)return 0;let r=mo[C(e)]??0,o=t.length>=2?t[1].start.getTime()-t[0].start.getTime():void 0;return(o?Math.min(o,r):r)/2},R={paid:{id:"paid",name:"paid",...St},saved:{id:"saved",name:"saved",...Tt}},Nt={variable:"--error-color",fallback:"#db4437"},go={gain:{variable:"--success-color",fallback:"#4caf50"},loss:Nt},Te=t=>t.value?.[1]??0,yo=t=>t.value?.[2],bo=.45,de={id:"before",name:"compared_series",variable:"--secondary-text-color",fallback:"#727272"},Ae=class extends w{static titleKey="title_cost_over_time";static getConfigElement(){return document.createElement(It)}_series(){let e=xt(this._result?.series??[],this._result?.period),r=this._colour(Nt),o=this._labels,s=this._result?.seriesBefore,a=_o(e,this._result?.period);return[...te([{...$t(R.paid,this._colour(R.paid),o),data:e.map(n=>Ct(n,Ft(n,n.actualCost,a)))},{...$t(R.saved,this._colour(R.saved),o),data:e.map(n=>{let i=Ft(n,n.costSavings,a),c=n.costSavings<0?Dt(r):void 0;return Ct(n,i,c)})}]),...s?.length?[{id:de.id,name:o[de.name],type:"line",symbol:"none",lineStyle:{type:"dashed",width:2},itemStyle:{color:this._colour(de)},data:s.map(n=>[n.start.getTime()+a,n.costAtGridPrice])}]:[]]}_caption(e){return`${super._caption(e)}${this._stillAccruingNote()}`+this._accrualNote()}_stillAccruingNote(){return(this._result?.series??[]).some(e=>e.accruing)?`<div class="hint">${this._labels.still_accruing}</div>`:""}_accrualNote(){return this._devices().length!==1||!this._period||C(this._period)!=="hour"?"":`<div class="hint">${this._labels.hourly_shape_estimate}</div>`}_tooltipFor(e,r){let o=(Array.isArray(e)?e:[e]).filter(c=>c.componentSubType==="bar"),s=o.filter(c=>Te(c)!==0);if(!s.length)return;let a=this._bucketAt(o.map(yo).find(c=>c!==void 0)),n=document.createElement("div");n.append(le(this._spanOf(a,r)));for(let c of s)n.append(this._tooltipRowFor(c,r));let i=o.reduce((c,l)=>c+Te(l),0);return s.length>1&&n.append($(this._labels.would_have_paid,h(i,r),void 0,{bold:!0})),a?.accruing&&n.append(Ot(this._labels.still_accruing)),n}_tooltipRowFor(e,r){let o=Te(e),a=e.seriesId===R.saved.id&&o<0?this._labels.lost:e.seriesName,n=e.seriesId===R.saved.id?T(o):"";return At(e.color,a,h(o,r),n?this._colour(go[n]):void 0)}_bucketAt(e){if(e!==void 0)return(this._result?.series??[]).find(r=>r.start.getTime()===e)}_spanOf(e,r){return!e||!this._period?"":at(e.start,C(this._period),r)}_headerChip(e){let r=this._result?.totals?.actualCost;return Number.isFinite(r)&&!this._isEmpty()?h(r,e):""}_axisBounds(){if(!this._period)return{};let{start:e,end:r}=this._period,o=new Date(r.getTime()-1);return C(this._period)==="hour"?o.setMinutes(30,0,0):(o.getHours()===0&&o.setHours(o.getHours()-1),o.setHours(0,0,0,0)),{min:e.getTime(),max:o.getTime()}}_options(e){let r=this._labels;return{xAxis:{type:"time",...this._axisBounds()},grid:{top:15,bottom:0,left:1,right:1,containLabel:!0},yAxis:{type:"value",name:K(e),nameGap:2,nameTextStyle:{align:"left"},boundaryGap:[0,0],splitNumber:5,splitLine:{show:!0},axisLabel:{formatter:o=>W(o,e),hideOverlap:!0}},tooltip:{trigger:"axis",axisPointer:{type:"shadow"},formatter:o=>this._tooltipFor(o,e)},legend:{show:!0,type:"custom",data:[R.paid,R.saved,...this._result?.seriesBefore?.length?[de]:[]].map(o=>({id:o.id,name:r[o.name],itemStyle:{color:this._colour(o)}}))}}}},Ct=(t,e,r=void 0)=>t.accruing?{value:e,itemStyle:{...r,opacity:bo}}:r?{value:e,itemStyle:r}:e,Ft=(t,e,r)=>[t.start.getTime()+r,e,t.start.getTime()],$t=({id:t,name:e},r,o)=>({id:t,name:o[e],type:"bar",stack:"cost",barMaxWidth:po,itemStyle:Dt(r)}),Dt=t=>({color:S(t,fo),borderColor:t,borderWidth:1}),Oe=class extends m{},vo=()=>{_(It,Oe),f(Rt,Ae,{name:"Home Energy Advisor: Cost over time",description:"What the period cost, stacked against what it would have cost at grid price."})};vo();var $e="hea",Ht="Home Energy Advisor",xo="mdi:home-lightning-bolt",Lt=`ll-strategy-dashboard-${$e}`,Mt=`ll-strategy-view-${$e}`,wo=[{type:"custom:hea-totals-card"},{type:"custom:hea-devices-card",sort_by:"actual_cost"},{type:"custom:hea-cost-over-time-card"},{type:"custom:hea-sources-card",sort_by:"energy_used"}],Eo=[{type:"custom:hea-device-costs-card"},{type:"custom:hea-distribution-card"},{type:"custom:hea-self-sufficiency-card"}],ko=t=>({...t,grid_options:{columns:"full",rows:"auto"}}),Gt=t=>({type:"grid",column_span:2,cards:t.map(ko)}),So=()=>({card:{type:"horizontal-stack",cards:[{type:"energy-date-selection",vertical_opening_direction:"up"},{type:"custom:hea-filter-card"}]},max_width:1600}),To=t=>({type:"sections",max_columns:4,sections:[{type:"grid",cards:[{type:"markdown",content:b(t).no_devices}]}]}),Ao=t=>y(t).length===0?To(t):{type:"sections",max_columns:4,sections:[Gt(wo),Gt(Eo)],footer:So()},Pt=async t=>(await A(t),Ao(t)),Ce=class extends HTMLElement{static async generate(e,r){return{views:[await Pt(r)]}}static noEditor=!0;static getCreateSuggestions(){return{title:Ht,icon:xo}}},Fe=class extends HTMLElement{static async generate(e,r){return Pt(r)}},Oo=t=>{globalThis.customStrategies=globalThis.customStrategies??[],globalThis.customStrategies.some(e=>e.type===t.type)||globalThis.customStrategies.push(t)},Co=()=>{customElements.get(Lt)||customElements.define(Lt,Ce),customElements.get(Mt)||customElements.define(Mt,Fe),Oo({type:$e,strategyType:"dashboard",name:Ht,description:"What each device cost to run, and what solar and the battery saved."})};Co();var jt=Object.keys(P),Fo=Object.keys(O),Ut=t=>{let e=new Map;for(let r of t){if(!r.upstream)continue;let o=e.get(r.upstream);o?o.push(r):e.set(r.upstream,[r])}return e},Bt=(t,e)=>({...t,key:`${t.key}${$o}`,name:`${t.name} ${e.device_untracked}`,upstream:t.key,untracked:!1,residualOf:t.key}),$o="__untracked",Ro=t=>{let e=Object.fromEntries(jt.map(r=>[r,0]));for(let r of t)for(let o of jt)e[o]+=r[o]??0;for(let r of Fo)e[r]=t.every(o=>typeof o[r]=="number")?t.reduce((o,s)=>o+s[r],0):void 0;return e.costSavings=e.costAtGridPrice-e.actualCost,e},he=(t,e)=>{let r=Ut(t);return r.size===0?t:t.flatMap(o=>r.has(o.key)?[Bt(o,e)]:[o])},zt=(t,e,r=o=>o)=>{let o=Ut(t);if(o.size===0)return r(t).map(n=>({device:n,depth:0}));let s=new Set(o.keys()),a=t.filter(n=>!n.upstream);return r(a).flatMap(n=>{if(!s.has(n.key))return[{device:n,depth:0}];let i=r([...o.get(n.key),Bt(n,e)]);return[{device:{...n,...Ro(i),subtotal:!0},depth:0},...i.map(c=>({device:c,depth:1}))]})};var E=Object.freeze(["#0072b2","#e69f00","#009e73","#cc79a7","#56b4e9","#d55e00","#8c6bb1","#3d9970"]),Io=Object.freeze(["#4b46b3","#8d9b1f","#00a2ab","#b07ad2","#7fa0ee","#a8761b","#b26596","#5b8f3f"]),Re=Object.freeze([E,Io]),xn=E.length*Re.length,j=Object.freeze({variable:"--secondary-text-color",fallback:"#8a8a8a"}),U=t=>{let e=(t??[]).filter(r=>!r.untracked).map(r=>r.key).sort(No);return new Map(e.map((r,o)=>{let s=Math.floor(o/E.length)%Re.length;return[r,Re[s][o%E.length]]}))},No=(t,e)=>t===e?0:t<e?-1:1;var ue=(t,e,r)=>{let o=t<0?e.lost_share:e.saved_share;return v(o,{percent:H(Math.abs(t),r)})},Do=({costSavings:t,costAtGridPrice:e})=>{if(!(!Number.isFinite(t)||!Number.isFinite(e))&&!(e<=0))return t/e},q=[{at:0,hue:3,light:48,dark:62},{at:.5,hue:35,light:46,dark:68},{at:1,hue:142,light:31,dark:76}],Wt={light:85,dark:70},Lo=.7,Kt=(t,e,r)=>t+(e-t)*r,Mo=.6,Go=(t,e)=>{let r=q.findIndex(i=>t<=i.at);if(r<=0)return{hue:q[0].hue,lightness:q[0][e]};let o=q[r-1],s=q[r],a=(t-o.at)/(s.at-o.at),n=r===1?a:a**Mo;return{hue:Kt(o.hue,s.hue,n),lightness:Kt(o[e],s[e],a)}},Yt=.05,I=t=>Math.round(t*10)/10,me=(t,{dark:e=!1}={})=>{let r=e?"dark":"light",o=a=>Math.max(0,a?.costAtGridPrice??0),s=Math.max(0,...(t??[]).map(o));return a=>{let n=Do(a??{});if(n===void 0||s<=0)return;let i=Math.min(1,o(a)/s),c=i*(1+Yt)/(i+Yt),l=Math.min(1,Math.max(0,n)),{hue:d,lightness:p}=Go(l,r),x=Wt[r]*c**Lo;return{rate:n,text:`hsl(${I(d)}, ${I(x)}%, ${I(p)}%)`,edge:`hsla(${I(d)}, ${I(Wt[r])}%, ${I(p)}%, ${I(c)})`}}};var tr="hea-device-costs-card",rr=`${tr}-editor`,Vt={variable:"--error-color",fallback:"#db4437"},Ho={variable:"--secondary-text-color",fallback:"#727272"},Po="earlier-period",jo=["auto","vertical","horizontal"],qt="(max-width: 767px)",Uo="paid",Bo="saved",Zt="before",zo=30,Wo=46,Ko=64,Yo=240,Vo=24,qo=12,Zo=2,Xo=10,Qo=300,Jo=120,es="40vw",ts={left:8,right:16,top:8,bottom:28,containLabel:!0},Xt=1.5,Qt=.8,Jt=.45,er=.22,rs=/:(?:paid|saved|before)$/,os={gain:{variable:"--success-color",fallback:"#4caf50"},loss:{variable:"--error-color",fallback:"#db4437"}},ss=(t,e,r,o,s,a)=>{let n=T(t.costSavings),i=document.createElement("div");i.append(le(e),$(o.paid,h(t.actualCost,r)),$(t.costSavings<0?o.lost:o.saved,h(t.costSavings,r),n?s(n):void 0),$(o.would_have_paid,h(t.costAtGridPrice,r)));let c=ns(a,r,o);c&&i.append(c);let l=as(t,r,o,s);l&&i.append(l);let d=is(t,r,o);return d&&i.append(d),i},ns=(t,e,r)=>{if(!t)return;let o=document.createElement("div");return o.style.marginTop="4px",o.style.color=t.text,o.textContent=ue(t.rate,r,e),o},as=(t,e,r,o)=>{let s=t.before?.actualCost;if(!Number.isFinite(s)||!Number.isFinite(t.actualCost))return;let a=t.actualCost-s,n=M("actualCost",a);return $(r.change,v(r.compared,{change:L(a,e),before:h(s,e)}),n?o(n):void 0)},is=({costFloor:t,costCeiling:e},r,o)=>{if(![t,e].every(a=>Number.isFinite(a)))return;let s=document.createElement("div");return s.style.marginTop="4px",s.style.opacity="0.75",s.textContent=v(o.range_device,{range:G([t,e],r)}),s},Ie=class extends w{static titleKey="title_device_costs";static narrowQuery=qt;static getConfigElement(){return document.createElement(rr)}_isEmpty(){return this._ranked().every(e=>!e.costAtGridPrice&&!e.actualCost)}_ranked(){return he(this._result?.devices??[],this._labels).sort((e,r)=>r.actualCost-e.actualCost||e.name.localeCompare(r.name))}_colourFor(e){if(e.untracked)return this._colour(j);let r=e.residualOf??e.key;return this._colours().get(r)??E[0]}_colours(){return U(y(this._hass))}_verdicts(){return me(this._ranked(),{dark:ae(this)})}_sideways(){let e=this._config?.layout;return e==="horizontal"?!0:e==="vertical"?!1:!!globalThis.matchMedia?.(qt)?.matches}_comparing(){return this._ranked().some(e=>e.before)}_series(){return te(this._sideways()?this._sidewaysSeries():this._standingSeries())}_sidewaysSeries(){let e=this._ranked(),r=this._colour(Vt),o=this._labels,s=a=>this._colourFor(a);return[{id:Uo,name:o.paid,type:"bar",stack:"cost",data:e.map(a=>({value:a.actualCost,itemStyle:{color:S(s(a),Qt)}}))},{id:Bo,name:o.saved,type:"bar",stack:"cost",data:e.map(a=>{let n=a.costSavings<0?r:s(a);return{value:a.costSavings,itemStyle:{color:S(n,er),borderColor:n,borderWidth:Xt}}})},...this._comparing()?[{id:Zt,name:o.compared_series,type:"bar",stack:"earlier",data:e.map(a=>({value:a.before?a.before.actualCost:null,itemStyle:{color:S(s(a),Jt)}}))}]:[]]}_standingSeries(){let e=this._colour(Vt);return this._ranked().flatMap(r=>{let o=this._colourFor(r),s=r.costSavings<0?e:o,a=r.name;return[{id:`${r.key}:paid`,name:a,type:"bar",stack:r.key,itemStyle:{color:S(o,Qt)},data:[r.actualCost]},{id:`${r.key}:saved`,name:a,type:"bar",stack:r.key,itemStyle:{color:S(s,er),borderColor:s,borderWidth:Xt},data:[r.costSavings]},...r.before?[{id:`${r.key}:before`,name:a,type:"bar",stack:`${r.key}:before`,itemStyle:{color:S(o,Jt)},data:[r.before.actualCost]}]:[]]})}_tooltipFor({seriesId:e,dataIndex:r},o){let s=this._ranked(),a=this._sideways()?s[r]:s.find(n=>n.key===String(e??"").replace(rs,""));return a?ss(a,a.name,o,this._labels,n=>this._colour(os[n]),this._verdicts()(a)):void 0}_earlierKey(){if(!this._comparing())return[];let e=this._labels.compared_series,r={color:this._colour(Ho)};return this._sideways()?[{id:Zt,name:e,itemStyle:r}]:[{id:Po,secondaryIds:this._ranked().filter(o=>o.before).map(o=>`${o.key}:before`),name:e,itemStyle:r}]}_chartHeight(){if(this._sideways()){let r=this._ranked().length,o=this._comparing()?Wo:zo;return`${Math.max(Yo,Ko+r*o)}px`}let e=Qo+this._legendHeight();return`clamp(${e}px, ${es}, ${e+Jo}px)`}_legendHeight(){let e=Math.min(this._ranked().length,Xo)+this._earlierKey().length;return Math.ceil(e/Zo)*Vo+qo}_options(e){return this._sideways()?this._sidewaysOptions(e):this._standingOptions(e)}_sidewaysOptions(e){let r=this._earlierKey();return{xAxis:{type:"value",name:K(e),axisLabel:{formatter:o=>W(o,e),hideOverlap:!0}},yAxis:{type:"category",data:this._ranked().map(o=>o.name),inverse:!0},grid:ts,tooltip:{trigger:"item",formatter:o=>this._tooltipFor(o,e)},...r.length?{legend:{show:!0,type:"custom",data:r}}:{}}}_standingOptions(e){return{xAxis:{type:"category",data:[Y(this._period,e)]},yAxis:{type:"value",name:K(e),nameGap:2,nameTextStyle:{align:"left"},axisLabel:{formatter:r=>W(r,e),hideOverlap:!0}},tooltip:{trigger:"item",formatter:r=>this._tooltipFor(r,e)},legend:{show:!0,type:"custom",data:[...this._ranked().map(r=>({id:`${r.key}:paid`,secondaryIds:[`${r.key}:saved`,...r.before?[`${r.key}:before`]:[]],name:r.name,itemStyle:{color:this._colourFor(r)}})),...this._earlierKey()]}}}},Ne=class extends m{_extraSchema(){return[{name:"layout",selector:{select:{mode:"dropdown",options:jo}}}]}},cs=()=>{_(rr,Ne),f(tr,Ie,{name:"Home Energy Advisor: Device costs (chart)",description:"What each device cost over the selected period, dearest first."})};cs();var ls=`${ie}
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
`,or=(t,e,r)=>{let o=t==="costSavings"?T(r):M(e,r);return o?` class="${o}"`:""},sr=t=>t?` style="box-shadow: inset ${ds} 0 0 ${t.edge}"`:"",ds="4px",N=class extends F{static columns=[];static sorts={};static defaultSort="";static cardStyle=ls;setConfig(e){let{sorts:r}=this.constructor;if(e.sort_by!==void 0&&!(e.sort_by in r))throw new Error(`\`sort_by\` must be one of: ${Object.keys(r).join(", ")}`);super.setConfig(e)}getCardSize(){return 3+Math.ceil((this._result?.devices.length??3)/2)}_columns(){return this.constructor.columns}_body(e){let r=this._columns(),o=this._verdictScale();return`
      <div class="scroll">
        <table>
          <thead><tr>${r.map(s=>this._heading(s,e)).join("")}</tr></thead>
          <tbody>${this._ranked().map(({device:s,depth:a})=>this._row(s,e,o,a)).join("")}</tbody>
          <tfoot>${this._total(e,o)}</tfoot>
        </table>
      </div>`}_verdictScale(){if(this._columns().some(e=>e.carriesVerdict))return me(this._result?.devices??[],{dark:ae(this)})}_heading({label:e},r){let o=this._labels;if(typeof e!="function")return`<th>${ce(e)}${o[e]}</th>`;let{text:s,unit:a}=e(r,o);return`<th>${s} <span class="unit">${g(a)}</span></th>`}_rank(e){let{sorts:r,defaultSort:o}=this.constructor,{field:s}=r[this._config?.sort_by??o];return[...e].sort((a,n)=>n[s]-a[s]||a.name.localeCompare(n.name))}_ranked(){return zt(this._result?.devices??[],this._labels,e=>this._rank(e))}_row(e,r,o,s){return`<tr${e.subtotal?' class="subtotal"':""}>${this._columns().map(n=>this._cell(n,e,r,o?.(e),s)).join("")}</tr>`}_cell({field:e,derive:r,format:o,tone:s,carriesVerdict:a,reveal:n},i,c,l,d){if(!o)return`<th scope="row"${d?' class="inside"':""}${sr(l)}>${g(i.name)}</th>`;let p=r?r(i):i[e],x=a?this._verdictOn(l,c):"",ee=this._revealed(o(p,c),n?.(i,c));return`<td${or(e,s,p)}${x}>${ee}</td>`}_revealed(e,r){return r?`<span class="reveal" tabindex="0" aria-label="${g(r.label)}">${e}<span class="revealed" aria-hidden="true">${g(r.text)}</span></span>`:e}_total(e,r){let o=this._sumOfShown(),s=r?.(o);return`<tr>${this._columns().map(({field:n,derive:i,format:c,tone:l,carriesVerdict:d})=>{if(!c)return`<th scope="row"${sr(s)}>${this._labels.total}</th>`;let p=i?i(o):o[n],x=d?this._verdictOn(s,e):"";return`<td${or(n,l,p)}${x}>${c(p,e)}</td>`}).join("")}</tr>`}_verdictOn(e,r){if(!e)return"";let o=ue(e.rate,this._labels,r);return` style="color: ${e.text}" title="${g(o)}"`}_sumOfShown(){let e=[...new Set(this._columns().flatMap(({field:n,fields:i,derive:c,format:l})=>l?c?i??[]:n?[n]:[]:[]))],r=he(this._result?.devices??[],this._labels),o=Object.fromEntries(this._columns().flatMap(({fields:n,field:i,readField:c})=>c?(n??[i]).map(l=>[l,c]):[])),s=n=>r.reduce((i,c)=>{for(let l of e){let d=n(c);i[l]+=o[l]?o[l](d,l):d[l]}return i},Object.fromEntries(e.map(i=>[i,0]))),a=s(n=>n);return r.length>0&&r.every(n=>n.before)&&(a.before=s(n=>n.before)),a}},pe=(t,e)=>[{name:"sort_by",selector:{select:{mode:"dropdown",options:Object.entries(t).map(([r,{label:o}])=>({value:r,label:e[o]}))}}}];var ar="hea-devices-card",ir=`${ar}-editor`,hs=({actualCost:t,energyUsed:e})=>e>0?t/e:void 0,cr=t=>Object.values(O).every(e=>e in(t.statistics??{})),Z={fields:["costFloor","costCeiling"],derive:({costFloor:t,costCeiling:e})=>[t,e],label:"range_column",format:G,readField:(t,e)=>Number.isFinite(t[e])?t[e]:t.actualCost},lr={fields:["actualCost"],derive:({actualCost:t,before:e})=>e&&Number.isFinite(t)&&Number.isFinite(e.actualCost)?t-e.actualCost:void 0,label:"change",format:L,tone:"actualCost"},fe={field:"actualCost",label:"paid",format:h,reveal:(t,e)=>{if(!cr(t)||!Z.fields.every(o=>Number.isFinite(t[o])))return null;let r=G(Z.derive(t),e);return{text:r,label:`${h(t.actualCost,e)} (${r})`}}},us={derive:t=>t.actualCost+(t.forgoneExport??0),label:"paid_with_forgone",format:h,reveal:fe.reveal},nr=[{field:"name",label:"device"},{field:"energyUsed",label:"energy",format:k},fe,lr,Z,{field:"costAtGridPrice",label:"would_have_paid",format:h,carriesVerdict:!0},{field:"costSavings",label:"saved",format:h},{derive:hs,label:(t,e)=>({text:e.rate,unit:lt(t)}),format:dt}],dr={actual_cost:{field:"actualCost",label:"paid"},cost_at_grid_price:{field:"costAtGridPrice",label:"would_have_paid"},cost_savings:{field:"costSavings",label:"saved"},energy_used:{field:"energyUsed",label:"energy_used"}},De=class extends N{static titleKey="title_devices";static columns=nr;static sorts=dr;static defaultSort="actual_cost";static cardStyle=`${N.cardStyle}
    .disclosure {
      margin-top: var(--hea-space-m);
      color: var(--secondary-text-color);
      font-size: 0.8em;
    }
  `;static getConfigElement(){return document.createElement(ir)}_columns(){let e=this._config?.range==="column"&&this._hasEveryBound(),o=this._config?.forgone!=="exclude"&&this._hasForgone()?us:fe,s=new Set;return e||s.add(Z),this._hasComparison()||s.add(lr),nr.filter(a=>!s.has(a)).map(a=>a!==fe?a:e?{...o,reveal:void 0}:o)}_hasComparison(){return(this._result?.devices??[]).some(e=>e.before)}_hasForgone(){return(this._result?.devices??[]).some(e=>(e.forgoneExport??0)>0)}_hasEveryBound(){let e=(this._result?.devices??[]).filter(cr);return e.length>0&&e.every(r=>Z.fields.every(o=>Number.isFinite(r[o])))}_body(e){return`${super._body(e)}${this._disclosure(e)}`}_disclosure(e){let r=this._labels;if(this._hasEveryBound())return`<div class="disclosure">${r.range_note}</div>`;let o=this._result?.wholeHome;if(!o)return"";let s=G([o.costFloor,o.costCeiling],e);return`<div class="disclosure">
      ${v(r.range_whole_home,{range:s})}
    </div>`}},Le=class extends m{_extraSchema(){let e=b(this._hass);return[...pe(dr,e),{name:"forgone",selector:{select:{mode:"dropdown",options:[{value:"include",label:e.editor_forgone_include},{value:"exclude",label:e.editor_forgone_exclude}]}}},{name:"range",selector:{select:{mode:"dropdown",options:[{value:"rollover",label:e.editor_range_rollover},{value:"column",label:e.editor_range_column}]}}}]}},ms=()=>{_(ir,Le),f(ar,De,{name:"Home Energy Advisor: Devices",description:"Every tracked device over the selected period, ordered by what it cost."})};ms();var Q="household",X=Object.freeze({source:0,household:1,floor:2,area:3,device:4}),hr=Object.freeze({cost:{field:"actualCost",sources:null},energy:{field:"energyUsed",sources:[{id:"grid",field:"energyFromGrid",variable:"--energy-grid-consumption-color",fallback:"#488fc2"},{id:"generation",field:"energyFromGeneration",variable:"--energy-solar-color",fallback:"#ff9800"},{id:"battery",field:"energyFromBattery",variable:"--energy-battery-out-color",fallback:"#4db6ac"}]}}),ps=t=>{let e=U(t);return r=>r.untracked?j.fallback:e.get(r.key)??E[0]},fs=({fallback:t})=>t,pr=(t,e,{metric:r="cost",colour:o=fs,deviceColour:s=ps(t)}={})=>{let{field:a,sources:n}=hr[r]??hr.cost,i=t.filter(u=>u[a]>0);if(i.length===0)return{nodes:[],links:[]};let c=new Map,l=new Map,d=[],p=[],x=0;i.forEach(u=>{let B=u[a];x+=B;let Ye=u.floorId?ur(c,u.floorId,u.floorName):null,_e=u.areaId?ur(l,u.areaId,u.areaName):null;Ye&&(Ye.value+=B),_e&&(_e.value+=B,_e.floorId??=u.floorId??null);let Ve=`device_${u.key}`;d.push({id:Ve,label:u.name,value:B,index:X.device,color:s(u),...ys(u)}),p.push({source:gs(u),target:Ve,value:B})});let ee=_s(n,i,e,o);return{nodes:[...ee,{id:Q,label:e.household,value:x,index:X.household},...mr(c,"floor_",X.floor),...mr(l,"area_",X.area),...d],links:[...ee.map(u=>({source:u.id,target:Q,value:u.value})),...bs(c,l),...p]}},_s=(t,e,r,o)=>(t??[]).map(s=>({id:`source_${s.id}`,label:r[s.id],value:e.reduce((a,n)=>a+(n[s.field]??0),0),index:X.source,color:o(s)})).filter(s=>s.value>0),ur=(t,e,r)=>(t.has(e)||t.set(e,{id:e,name:r||e,value:0}),t.get(e)),gs=t=>t.areaId?`area_${t.areaId}`:t.floorId?`floor_${t.floorId}`:Q,ys=t=>{let e=t.statistics?.actual_cost;return e?{entityId:e}:{}},mr=(t,e,r)=>[...t.values()].map(o=>({id:`${e}${o.id}`,label:o.name,value:o.value,index:r})),bs=(t,e)=>[...[...t.values()].map(r=>({source:Q,target:`floor_${r.id}`,value:r.value})),...[...e.values()].map(r=>({source:r.floorId?`floor_${r.floorId}`:Q,target:`area_${r.id}`,value:r.value}))];var _r="hea-distribution-card",gr=`${_r}-editor`,J={cost:{titleKey:"title_distribution",emptyKey:"no_cost_in_period",format:h},energy:{titleKey:"title_distribution_energy",emptyKey:"no_energy_in_period",format:k}},fr="(max-width: 767px)",vs="400px",xs=88,ws=240,Es=["auto","horizontal","vertical"],Me=class extends w{static titleKey="title_distribution";static chartTag="ha-sankey-chart";static bearingCard={type:"energy-sankey"};static narrowQuery=fr;static cardStyle=`
    ha-sankey-chart { display: block; min-height: 240px; }
  `;static getConfigElement(){return document.createElement(gr)}_isEmpty(){return this._layout().nodes.length===0}_verticalHeight({nodes:e}){let r=new Set(e.map(o=>o.index)).size;return`${Math.max(ws,r*xs)}px`}_metric(){return J[this._config?.metric]?this._config.metric:"cost"}_titleKey(){return J[this._metric()].titleKey}_emptyKey(){return J[this._metric()].emptyKey}_layout(){let e=U(y(this._hass));return pr(this._result?.devices??[],this._labels,{metric:this._metric(),colour:r=>this._colour(r),deviceColour:r=>r.untracked?this._colour(j):e.get(r.key)??E[0]})}_chartMarkup(){return"<ha-sankey-chart></ha-sankey-chart>"}_draw(e){e.data=this._layout(),e.vertical=this._isVertical(),e.style.height=this._isVertical()?this._verticalHeight(e.data):vs;let r=this._chartLocale(),{format:o}=J[this._metric()];e.valueFormatter=s=>o(s,r),this.toggleAttribute("data-vertical",e.vertical)}_isVertical(){let e=this._config?.layout;return e==="vertical"?!0:e==="horizontal"?!1:!!globalThis.matchMedia?.(fr)?.matches}},Ge=class extends m{_extraSchema(){return[{name:"metric",selector:{select:{mode:"dropdown",options:Object.keys(J)}}},{name:"layout",selector:{select:{mode:"dropdown",options:Es}}}]}},ks=()=>{_(gr,Ge),f(_r,Me,{name:"Home Energy Advisor: Cost distribution",description:"Where the period's cost went, by floor, room and device."})};ks();var yr="hea-filter-card",br=`${yr}-editor`,Ss=[{kind:"area",label:"filter_rooms",id:"areaId",name:"areaName"},{kind:"floor",label:"filter_floors",id:"floorId",name:"floorName"}],D=({kind:t,id:e})=>`${t}:${e??""}`,Ts=t=>{let[e,r]=[t.slice(0,t.indexOf(":")),t.slice(t.indexOf(":")+1)];return{kind:e,id:r===""?null:r}},He=class extends HTMLElement{constructor(){super(),this.attachShadow({mode:"open"})}setConfig(e){this._config=e,this._render()}set hass(e){this._hass=e,A(e).then(()=>this._renderIfChanged()),this._renderIfChanged()}getCardSize(){return 1}static getConfigElement(){return document.createElement(br)}connectedCallback(){this._render(),this._unfilter??=se(this._config?.collection_key,()=>this._renderIfChanged())}_signature(){return JSON.stringify([this._allDevices().map(e=>[e.key,e.name,e.areaId,e.areaName,e.floorId,e.floorName,e.labels]),D(z(this._config?.collection_key)),this._labels.filter_rooms])}_renderIfChanged(){this._signature()!==this._drawn&&this._render()}disconnectedCallback(){this._unfilter?.(),this._unfilter=null}get _labels(){return b(this._hass)}_devices(){return y(this._hass).filter(e=>!e.untracked)}_allDevices(){return y(this._hass)}_optionsFor({kind:e,id:r,name:o},s){let a=new Map,n=!1;for(let c of s)c[r]?a.set(c[r],c[o]??c[r]):n=!0;let i=[...a.entries()].map(([c,l])=>({value:D({kind:e,id:c}),text:l})).sort((c,l)=>c.text.localeCompare(l.text));return n&&i.push({value:D({kind:e,id:null}),text:this._labels.filter_unfiled}),i}_labelOptions(e){let r=et(this._hass);return[...new Set(e.flatMap(s=>s.labels??[]))].map(s=>({value:D({kind:"label",id:s}),text:r[s]??s})).sort((s,a)=>s.text.localeCompare(a.text))}_deviceOptions(){return this._allDevices().map(e=>({value:D({kind:"device",id:e.key}),text:e.name})).sort((e,r)=>e.text.localeCompare(r.text))}_groups(){let e=this._devices(),r=Ss.map(s=>({label:this._labels[s.label],options:this._optionsFor(s,e)})),o=this._labelOptions(e);return o.length&&r.push({label:this._labels.filter_labels,options:o}),r.push({label:this._labels.filter_devices,options:this._deviceOptions()}),r.filter(s=>s.options.length>0)}_render(){let e=this._labels,r=this._devices();this._drawn=this._signature();let o=r.length?this._control(e):`<p class="message">${e.no_devices}</p>`;this.shadowRoot.innerHTML=`
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
    `;let s=this.shadowRoot.querySelector("select");s&&(s.value=D(z(this._config?.collection_key)),s.addEventListener("change",()=>ot(this._config?.collection_key,Ts(s.value))))}_control(e){let r=this._groups().map(o=>`<optgroup label="${g(o.label)}">${o.options.map(s=>`<option value="${g(s.value)}">${g(s.text)}</option>`).join("")}</optgroup>`).join("");return`<div class="body">
      <span class="label">${e.title_filter}</span>
      <select>
        <option value="${D({kind:"all",id:null})}">${g(e.filter_everything)}</option>
        ${r}
      </select>
    </div>`}},Pe=class extends m{},As=()=>{_(br,Pe),f(yr,He,{name:"Home Energy Advisor: Filter",description:"Narrow every Home Energy Advisor card on the page to a room, a floor, a label or one device."})};As();var xr="hea-self-sufficiency-card",wr=`${xr}-editor`,vr=["energyUsed","energyFromGrid","energyFromGeneration","energyFromBattery"],Os={maximumFractionDigits:0},Cs=.005,je=class extends w{static titleKey="title_self_sufficiency";static chartTag="ha-gauge";static bearingCard={type:"energy-self-sufficiency-gauge"};static emptyKey="no_energy_in_period";static cardStyle=`
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
  `;static getConfigElement(){return document.createElement(wr)}getCardSize(){return 4}_isEmpty(){return this._totals().energyUsed<=0}_totals(){return(this._result?.devices??[]).reduce((e,r)=>{for(let o of vr)e[o]+=r[o];return e},Object.fromEntries(vr.map(e=>[e,0])))}_shares(){let e=this._totals(),r=e.energyUsed,o=i=>e[i]/r,s=o("energyFromGeneration"),a=o("energyFromBattery"),n=o("energyFromGrid");return{generation:s,battery:a,grid:n,unaccounted:Math.max(0,1-s-a-n)}}_body(e){let r=super._body(e);return!this._chartReady||this._isEmpty()?r:`${r}${this._breakdown(e)}`}_chartMarkup(){return`<ha-gauge></ha-gauge>
      <div class="headline">${this._labels.from_generation}</div>`}_breakdown(e){let{battery:r,grid:o,unaccounted:s}=this._shares();return`<div class="shares">${[{label:"from_battery",value:r},{label:"from_grid",value:o},{label:"unaccounted",value:s}].filter(({label:n,value:i})=>n!=="unaccounted"||i>Cs).map(({label:n,value:i})=>`
        <div class="share">
          <span class="label">${this._labels[n]}</span>
          <span class="value" data-share="${n}">${H(i,e)}</span>
        </div>`).join("")}</div>
      <div class="note">${this._labels.self_sufficiency_note}</div>`}_draw(e){e.min=0,e.max=100,e.value=this._shares().generation*100,e.label="%",e.formatOptions=Os,e.locale=this._hass?.locale}},Ue=class extends m{},Fs=()=>{_(wr,Ue),f(xr,je,{name:"Home Energy Advisor: Self-sufficiency",description:"What share of the selected period's energy came from the household's own generation."})};Fs();var Er="hea-sources-card",kr=`${Er}-editor`,$s=({energyFromGrid:t,energyUsed:e})=>e>0&&t>=0&&t<=e?t/e:void 0,Rs=[{field:"name",label:"device"},{field:"energyUsed",label:"energy",format:k},{field:"energyFromGrid",label:"grid",format:k},{field:"energyFromGeneration",label:"generation",format:k},{field:"energyFromBattery",label:"battery",format:k},{derive:$s,label:"from_grid",format:H}],Sr={energy_used:{field:"energyUsed",label:"energy_used"},energy_from_grid:{field:"energyFromGrid",label:"from_grid"},energy_from_generation:{field:"energyFromGeneration",label:"from_generation"},energy_from_battery:{field:"energyFromBattery",label:"from_battery"}},Be=class extends N{static titleKey="title_sources";static columns=Rs;static sorts=Sr;static defaultSort="energy_used";static getConfigElement(){return document.createElement(kr)}},ze=class extends m{_extraSchema(){return pe(Sr,b(this._hass))}},Is=()=>{_(kr,ze),f(Er,Be,{name:"Home Energy Advisor: Energy sources",description:"Grid, generation and battery behind each device's energy over the period."})};Is();var Tr="hea-totals-card",Ar=`${Tr}-editor`,Ns=[{key:"actualCost",label:"paid"},{key:"costAtGridPrice",label:"would_have_paid"},{key:"costSavings",label:"saved"}],We=class extends F{static titleKey="title_totals";static cardStyle=`${ie}
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
  `;static getConfigElement(){return document.createElement(Ar)}getCardSize(){return 3}_body(e){let r=this._result?.totals;return`<div class="figures">${Ns.map(({key:s,label:a})=>{let n=r?.[s],i=s==="costSavings"?T(n):"",c=i?` ${i}`:"";return`
        <div class="figure">
          <span class="label">${ce(a)}${this._labels[a]}</span>
          <span class="value${c}" data-figure="${s}">${h(n,e)}</span>
          ${this._comparedTo(s,n,e)}
        </div>`}).join("")}</div>`}_comparedTo(e,r,o){let s=this._result?.totals?.before?.[e];if(!Number.isFinite(s)||!Number.isFinite(r))return"";let a=M(e,r-s);return`<span class="${a?`compare ${a}`:"compare"}" data-compare="${e}">${v(this._labels.compared,{change:L(r-s,o),before:h(s,o)})}</span>`}},Ke=class extends m{},Ds=()=>{_(Ar,Ke),f(Tr,We,{name:"Home Energy Advisor: Totals",description:"What the selected period cost, what it would have cost at grid price, and the difference."})};Ds();
