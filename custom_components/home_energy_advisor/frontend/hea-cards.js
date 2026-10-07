var Or=[4,4,0,0],Cr=[0,0,4,4],qe=t=>t!==null&&typeof t=="object"&&!Array.isArray(t),Fr=t=>{let e=qe(t)?t.value:t;return Array.isArray(e)?e[1]:e},_e=(t,e)=>{let r=qe(t)?{...t}:{value:t};return{...r,itemStyle:{...r.itemStyle,...e}}},te=t=>{let e=Math.max(...t.map(({data:s})=>s.length),0),r=t.map(({data:s})=>[...s]);for(let s of $r(t))for(let o=0;o<e;o++)Rr(r,o,s);return t.map((s,o)=>({...s,data:r[o]}))},$r=t=>{let e=new Map;return t.forEach((r,s)=>{let o=r.stack??Symbol(s),a=e.get(o);a?a.push(s):e.set(o,[s])}),[...e.values()]},Rr=(t,e,r)=>{let s=!1,o=!1;for(let a=r.length-1;a>=0;a--){let n=r[a],i=t[n][e];if(i===void 0)continue;let c=Fr(i);c?c>0&&!s?(t[n][e]=_e(i,{borderRadius:Or}),s=!0):c<0&&!o&&(t[n][e]=_e(i,{borderRadius:Cr}),o=!0):t[n][e]=_e(i,{borderWidth:0})}};var Ze="_energy",ge="energy_";var Ir=(t,e)=>{let r=t||(e?`${ge}${e}`:"");return r?r.startsWith(ge)?`_${r}`:`_${ge}${r}`:Ze},Nr=(t,e)=>typeof t=="string"&&t.startsWith(Ze)&&e!==null&&typeof e=="object"&&typeof e.subscribe=="function"&&"start"in e,Dr=(t=new Date)=>{let e=new Date(t);return e.setDate(e.getDate()-30),e.setHours(0,0,0,0),{start:e,end:t,fallback:!0}},Lr=t=>{let e=t?.connection;if(!e)return{};let r={};for(let s of Object.keys(e)){let o;try{o=e[s]}catch{continue}Nr(s,o)&&(r[s]=o)}return r},Mr=(t,e)=>{let r=Lr(t),s=Ir(e,t?.panelUrl);if(r[s])return r[s];let[o]=Object.values(r);return o??null},Gr=t=>t?.startCompare&&t?.endCompare?{compare:{start:t.startCompare,end:t.endCompare,mode:t.compareMode}}:{},Xe=(t,e,r)=>{let s=null,o=null,a=0,n=t,i=l=>{if(s)return!0;let d=Mr(l,e);if(!d)return!1;let p=x=>r({start:d.start,end:d.end,fallback:!1,...Gr(x)});return s=d.subscribe(p),p(),!0},c=()=>{o=setTimeout(()=>{o=null,a+=1,!i(n)&&a<40&&c()},250)};return r(Dr()),i(t)||c(),{retry:l=>(l&&(n=l),i(n)),unsubscribe:()=>{o&&clearTimeout(o),o=null;try{typeof s=="function"&&s()}catch{}s=null}}};var re="sensor.home_energy_advisor_devices",Hr="home_energy_advisor",se=t=>{if(t?.states?.[re])return re;let e=t?.entities;if(!e)return re;for(let[r,s]of Object.entries(e))if(s?.platform===Hr&&Array.isArray(t?.states?.[r]?.attributes?.devices))return r;return re},y=(t,e=void 0)=>{let r=t?.states?.[e??se(t)]?.attributes?.devices;return Array.isArray(r)?r.filter(s=>s?.key).map(tt):[]},Qe=(t,e=void 0)=>{let r=t?.states?.[e??se(t)]?.attributes?.whole_home;return r?.key?tt(r):null},Je=(t,e=void 0)=>{let r=t?.states?.[e??se(t)]?.attributes?.settled_until;if(typeof r!="string")return null;let s=new Date(r);return Number.isNaN(s.getTime())?null:s},et=(t,e=void 0)=>{let r=t?.states?.[e??se(t)]?.attributes?.labels;return r&&typeof r=="object"?r:{}},tt=t=>({key:t.key,name:t.name||t.key,deviceId:t.device_id??null,untracked:!!t.untracked,statistics:t.statistics??{},areaId:t.area_id??null,areaName:t.area_name??null,floorId:t.floor_id??null,floorName:t.floor_name??null,upstream:t.upstream??null,labels:Array.isArray(t.labels)?t.labels:[]});var rt=Object.freeze({kind:"all",id:null}),Pr={area:"areaId",floor:"floorId"},ye=new Map,be=t=>(ye.has(t)||ye.set(t,{filter:rt,listeners:new Set}),ye.get(t)),W=t=>be(t).filter,oe=(t,e)=>{let{listeners:r}=be(t);return r.add(e),()=>r.delete(e)},st=(t,e)=>{let r=be(t),s={kind:e?.kind??"all",id:e?.id??null};if(!(s.kind===r.filter.kind&&s.id===r.filter.id)){r.filter=s;for(let o of r.listeners)try{o(s)}catch(a){console.warn("home-energy-advisor: a card could not follow the filter",a)}}},ot=(t,e)=>{let{kind:r,id:s}=e??rt;if(r==="all")return!0;if(r==="device")return t.key===s;if(t.untracked)return!1;if(r==="label")return(t.labels??[]).includes(s);let o=Pr[r];return o?(t[o]??null)===s:!0};var jr={day:"numeric",month:"short",year:"numeric"},ne=t=>({language:t?.locale?.language||void 0,currency:t?.config?.currency||void 0,timeFormat:t?.locale?.time_format||void 0,timeZone:t?.locale?.time_zone==="server"?t?.config?.time_zone:void 0}),Ur=({timeFormat:t,language:e})=>{if(t==="language"||t==="system"||!t){let r=t==="system"?void 0:e;return new Date("January 1, 2023 22:00:00").toLocaleString(r).includes("10")}return t==="12"},nt=(t,e)=>new Intl.DateTimeFormat(e.language,{hour:"numeric",minute:"2-digit",hourCycle:Ur(e)?"h12":"h23",timeZone:e.timeZone}).format(t),Br=(t,e)=>new Intl.DateTimeFormat(e.language,{weekday:"short",month:"short",day:"numeric",timeZone:e.timeZone}).format(t),Wr={hour:3600*1e3},at=(t,e,r)=>{let s=Wr[e];if(!s)return Br(t,r);let o=new Date(t.getTime()+s);return`${nt(t,r)} \u2013 ${nt(o,r)}`},u=(t,{language:e,currency:r})=>{if(typeof t!="number"||!Number.isFinite(t))return"-";let s=r?{style:"currency",currency:r}:{minimumFractionDigits:2,maximumFractionDigits:2};return new Intl.NumberFormat(e,s).format(t)},L=(t,{language:e,currency:r})=>{if(typeof t!="number"||!Number.isFinite(t))return"-";let s=r?{style:"currency",currency:r,signDisplay:"exceptZero"}:{minimumFractionDigits:2,maximumFractionDigits:2,signDisplay:"exceptZero"};return new Intl.NumberFormat(e,s).format(t)},zr=new Set(["actualCost","costAtGridPrice","energyUsed"]),Kr=new Set(["costSavings"]),T=t=>typeof t!="number"||!Number.isFinite(t)||t===0?"":t>0?"gain":"loss",M=(t,e)=>typeof e!="number"||!Number.isFinite(e)||e===0?"":zr.has(t)?e<0?"gain":"loss":Kr.has(t)?e>0?"gain":"loss":"",G=(t,e)=>{if(!Array.isArray(t))return"-";let[r,s]=t;if(![r,s].every(n=>Number.isFinite(n)))return"-";if(r===s)return u(r,e);let[o,a]=r<=s?[r,s]:[s,r];return`${u(o,e)} - ${u(a,e)}`},k=(t,{language:e})=>typeof t!="number"||!Number.isFinite(t)?"-":`${new Intl.NumberFormat(e,{maximumFractionDigits:1}).format(t)} kWh`,it={EUR:{symbol:"c",per:100},USD:{symbol:"\xA2",per:100},GBP:{symbol:"p",per:100}},z=(t,{language:e})=>typeof t!="number"||!Number.isFinite(t)?"-":new Intl.NumberFormat(e,{minimumFractionDigits:t===0?0:2,maximumFractionDigits:2}).format(t),K=({language:t,currency:e})=>e?ct(t,e):"",ct=(t,e)=>new Intl.NumberFormat(t,{style:"currency",currency:e}).formatToParts(0).find(r=>r.type==="currency")?.value??"",lt=({language:t,currency:e})=>{if(!e)return"/kWh";let r=it[e];return`${r?r.symbol:ct(t,e)}/kWh`},dt=(t,{language:e,currency:r})=>{if(typeof t!="number"||!Number.isFinite(t))return"-";let s=r?it[r]:void 0;return new Intl.NumberFormat(e,{minimumFractionDigits:s?1:0,maximumFractionDigits:s?2:3}).format(s?t*s.per:t)},H=(t,{language:e})=>typeof t!="number"||!Number.isFinite(t)?"-":new Intl.NumberFormat(e,{style:"percent",maximumFractionDigits:0}).format(t),g=t=>String(t).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#39;"),Y=(t,{language:e})=>t?new Intl.DateTimeFormat(e,jr).formatRange(t.start,t.end):"";var ht="common",mt="home_energy_advisor",ut=`component.${mt}.${ht}.card_`,xe=Object.freeze({paid:"Paid",would_have_paid:"Would have paid",saved:"Saved",lost:"Lost",range_column:"Paid (min-max)",range_note:"Paid (min-max) is the widest range these readings allow, not a typical error: a meter that reports every 30-90 minutes leaves the exact moment of use unknown.",range_whole_home:"What you paid could honestly sit between {range} - the widest these readings allow, not a typical error.",range_device:"What you paid could be between {range}.",compared:"{change} vs {before}",compared_period:"{period} vs {compared}",saved_share:"{percent} of what you would have paid was saved.",lost_share:"{percent} more was paid than the grid would have cost.",change:"Change",compared_series:"Earlier period",device:"Device",energy:"Energy",rate:"Rate",total:"Total",grid:"Grid",generation:"Generation",battery:"Battery",from_grid:"From the grid",from_generation:"From generation",from_battery:"From the battery",energy_used:"Energy used",unaccounted:"Unaccounted",self_sufficiency_note:"Battery energy is counted on its own: it was charged from generation or from the grid, and these readings cannot say which.",household:"Household",title_totals:"Cost summary",title_devices:"Cost by device",title_device_costs:"What each device cost",title_cost_over_time:"Cost over time",title_sources:"Where the energy came from",title_self_sufficiency:"Self-sufficiency",title_distribution:"Where the cost went",title_distribution_energy:"Where the energy went",no_devices:"No devices are being tracked yet.",no_devices_in_filter:"No tracked device matches what the page is showing.",title_filter:"Show",filter_everything:"Everything",filter_rooms:"Rooms",filter_floors:"Floors",filter_labels:"Labels",filter_devices:"Devices",filter_unfiled:"Not in one",device_untracked:"Untracked",hourly_shape_estimate:"One device's hourly shape is an estimate: each meter reading is spread across the hours it spanned, so cost may not land in the hour the energy was used.",still_accruing:"The last interval is still being counted, so its bar will grow. Figures are complete about twenty minutes behind the clock, which is how long meters are given to report.",statistics_failed:"Statistics could not be loaded.",no_picker:"Add an Energy date picker card to choose the range.",chart_not_loaded:"Home Assistant's chart component is not loaded. Adding any energy or statistics card to this dashboard will load it.",no_cost_in_period:"No cost recorded in this period.",no_energy_in_period:"No energy recorded in this period.",editor_title:"Title",editor_collection_key:"Energy period (collection key)",editor_devices:"Devices (all, if none are chosen)",editor_sort_by:"Order by",editor_layout:"Layout",editor_metric:"Measure by",editor_range:"Show the cost range as",editor_range_rollover:"A rollover on Paid",editor_range_column:"Its own column"}),ve=new Map,pt=new Map,ft=t=>t?.locale?.language||t?.language||"en",A=t=>{let e=ft(t);return ve.has(e)||ve.set(e,Yr(t,e).then(r=>(pt.set(e,r),r))),ve.get(e)},Yr=async(t,e)=>{try{let{resources:r}=await t.callWS({type:"frontend/get_translations",language:e,category:ht,integration:[mt]});return Object.freeze({...xe,...Vr(r)})}catch(r){return console.warn("home-energy-advisor: falling back to English labels",r),xe}},b=t=>pt.get(ft(t))??xe,Vr=t=>Object.fromEntries(Object.entries(t??{}).filter(([e,r])=>e.startsWith(ut)&&r).map(([e,r])=>[e.slice(ut.length),r])),v=(t,e)=>Object.entries(e).reduce((r,[s,o])=>r.replaceAll(`{${s}}`,o),t);var P=Object.freeze({energyUsed:"energy_used",actualCost:"actual_cost",costAtGridPrice:"cost_at_grid_price",energyFromGrid:"energy_from_grid",energyFromGeneration:"energy_from_generation",energyFromBattery:"energy_from_battery"}),O=Object.freeze({costFloor:"lowest_possible_cost",costCeiling:"highest_possible_cost"}),we=()=>Object.fromEntries(Object.keys(P).map(t=>[t,0])),yt=1440*60*1e3,bt={hour:3600*1e3,day:yt},qr=2,V=(t,e)=>t?.statistics?.[e],Zr=(t,e)=>{let r=t.flatMap(s=>[...Object.values(P),...Object.values(O)].map(o=>V(s,o)).filter(Boolean));return!e?.statistics||t.length===0?r:[...r,...Object.values(O).map(s=>V(e,s)).filter(Boolean)]},vt=(t,e)=>{if(!e)return t;let r=new Map(e.devices.map(s=>[s.key,s]));return{...t,totals:{...t.totals,before:e.totals},devices:t.devices.map(s=>({...s,before:r.get(s.key)})),seriesBefore:Xr(e.series,t.period,e.period)}},Xr=(t,e,r)=>{if(!t?.length)return;let s=e.start.getTime()-r.start.getTime();return t.map(o=>({...o,start:new Date(o.start.getTime()+s),actualStart:o.start}))},C=({start:t,end:e})=>e-t>qr*yt?"day":"hour",_t=(t,e,r)=>{if(e!=="day")return new Date(t.getTime()+r*bt.hour);let s=new Date(t);return s.setDate(s.getDate()+r),s},xt=(t,e)=>{if(!t.length||!e)return t;let r=C(e),s=new Map(t.map(n=>[n.start.getTime(),n])),o=t[0].start,a=[];for(let n=0;;n--){let i=_t(o,r,n);if(i.getTime()<e.start.getTime())break;a.push(s.get(i.getTime())??gt(i))}a.reverse();for(let n=1;;n++){let i=_t(o,r,n);if(i.getTime()>=e.end.getTime())break;a.push(s.get(i.getTime())??gt(i))}return a},gt=t=>({...we(),start:t,costSavings:0,accruing:!1}),Ee=async(t,e,r,s,o=null)=>{let a=Zr(e,s),n=a.length?await t.callWS({type:"recorder/statistics_during_period",start_time:r.start.toISOString(),end_time:r.end.toISOString(),statistic_ids:a,period:C(r),types:["change"]}):{},i=e.map(c=>Jr(c,n,r));return{period:r,devices:i,totals:es(i),wholeHome:wt(s,n,r),series:Qr(e,n,r,o)}},wt=(t,e,r)=>{if(!t)return;let s={};for(let[o,a]of Object.entries(O)){let n=e?.[V(t,a)];if(!Array.isArray(n))return;s[o]=kt(n,r)}return s},Qr=(t,e,r,s)=>{let o=new Map;for(let n of t)for(let[i,c]of Object.entries(P)){let l=e?.[V(n,c)];for(let d of Et(l,r)){let p=o.get(d.start)??we();p[i]+=d.change,o.set(d.start,p)}}let a=bt[C(r)]??0;return[...o.entries()].sort(([n],[i])=>n-i).map(([n,i])=>({...i,start:new Date(n),costSavings:i.costAtGridPrice-i.actualCost,accruing:s?n+a>s.getTime():!1}))},Jr=(t,e,r)=>{let s=Object.fromEntries(Object.entries(P).map(([o,a])=>[o,kt(e?.[V(t,a)],r)]));return{...t,...s,...wt(t,e,r),costSavings:s.costAtGridPrice-s.actualCost}},Et=(t,{start:e,end:r})=>{if(!Array.isArray(t))return[];let s=[];for(let o of t){let a=new Date(o.start).getTime();a<e.getTime()||a>=r.getTime()||typeof o.change=="number"&&s.push({start:a,change:o.change})}return s},kt=(t,e)=>Et(t,e).reduce((r,s)=>r+s.change,0),es=t=>({...t.reduce((r,s)=>{for(let o of Object.keys(r))r[o]+=s[o];return r},{...we(),costSavings:0}),...ts(t)}),ts=t=>{let e=Object.keys(O);return!t.length||!t.every(r=>e.every(s=>s in r))?{}:Object.fromEntries(e.map(r=>[r,t.reduce((s,o)=>s+o[r],0)]))};var rs=`
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
`,ss=`
  .loss { color: var(--error-color, #db4437); }
  .gain { color: var(--success-color, #4caf50); }
`,F=class extends HTMLElement{static cardStyle="";static titleKey="";_titleKey(){return this.constructor.titleKey}get _labels(){return b(this._hass)}constructor(){super(),this.attachShadow({mode:"open"}),this._state="loading",this._request=0}setConfig(e){if(e.devices!==void 0&&!Array.isArray(e.devices))throw new Error("`devices` must be a list of device keys");this._config=e,this._render()}set hass(e){this._hass=e,this._subscription?this._subscription.retry(e):this._subscribe(),this._refetchIfDevicesChanged()}connectedCallback(){this._render(),this._hass&&!this._subscription&&this._subscribe()}disconnectedCallback(){this._subscription?.unsubscribe(),this._subscription=null,this._unfilter?.(),this._unfilter=null}_subscribe(){this._subscription=Xe(this._hass,this._config?.collection_key,e=>{this._period=e,this._scheduleFetch()}),this._unfilter=oe(this._config?.collection_key,()=>this._scheduleFetch())}_scheduleFetch(){this._fetchPending||(this._fetchPending=!0,queueMicrotask(()=>{this._fetchPending=!1,this._fetch()}))}_refetchIfDevicesChanged(){let e=this._devices().map(r=>r.key).join(",");e!==this._deviceKeys&&(this._deviceKeys=e,this._period&&this._scheduleFetch())}_devices(){let e=y(this._hass),r=this._config?.devices,s=r?e.filter(a=>r.includes(a.key)):e,o=this._filter();return s.filter(a=>ot(a,o))}_filter(){return W(this._config?.collection_key)}_isFiltered(){return!!this._config?.devices||this._filter().kind!=="all"}async _fetch(){if(!this._hass||!this._period)return;let e=this._devices(),r=++this._request;if(await A(this._hass),e.length===0){this._state="empty",this._render();return}let s=this._isFiltered()?void 0:Qe(this._hass);try{let o=Je(this._hass),[a,n]=await Promise.all([Ee(this._hass,e,this._period,s,o),this._period.compare?Ee(this._hass,e,this._period.compare,s):void 0]);if(r!==this._request)return;this._result=vt(a,n),this._state="ready"}catch(o){if(r!==this._request)return;this._state="error",console.error(`${this.localName}: could not load statistics`,o)}this._render()}_render(){let e=ne(this._hass);this.shadowRoot.innerHTML=`
      <style>${rs}${this.constructor.cardStyle}${ss}</style>
      <ha-card>
        <div class="body" data-state="${this._state}">${this._content(e)}</div>
      </ha-card>
    `;let r=this._config?.title??this._labels[this._titleKey()];r&&this._writeHeader(r,e),this._afterRender()}_writeHeader(e,r){let s=this.shadowRoot.querySelector("ha-card"),o=this._headerChip(r);if(o===void 0){s.setAttribute("header",e);return}s.insertAdjacentHTML("afterbegin",`<div class="card-header" style="display: flex; justify-content: space-between;
         align-items: center; gap: var(--hea-space-s); padding-bottom: 0;">
        <span class="title">${g(e)}</span>
        <span class="chip">${g(o)}</span>
      </div>`)}_headerChip(){}_afterRender(){}_content(e){return this._state==="empty"?`<p class="message">${this._labels.no_devices}</p>`:this._state==="error"?`<p class="message">${this._labels.statistics_failed}</p>`:`${this._body(e)}${this._caption(e)}`}_caption(e){let r=this._period?.fallback?`<div class="hint">${this._labels.no_picker}</div>`:"";return`<div class="period">${this._periodLabel(e)}</div>${r}`}_periodLabel(e){let r=Y(this._period,e),s=this._period?.compare;return s?v(this._labels.compared_period,{period:r,compared:Y(s,e)}):r}},f=(t,e,{name:r,description:s})=>{customElements.get(t)||customElements.define(t,e),globalThis.customCards=globalThis.customCards??[],globalThis.customCards.some(o=>o.type===t)||globalThis.customCards.push({type:t,name:r,description:s})};var os={title:"editor_title",collection_key:"editor_collection_key",devices:"editor_devices",sort_by:"editor_sort_by",layout:"editor_layout",metric:"editor_metric",range:"editor_range"},m=class extends HTMLElement{constructor(){super(),this.attachShadow({mode:"open"})}setConfig(e){this._config=e,this._render()}set hass(e){this._hass=e,this._render(),A(e).then(()=>this._render())}_extraSchema(){return[]}_render(){if(!this._config)return;let e=this.shadowRoot.querySelector("ha-form");e||(e=document.createElement("ha-form"),e.computeLabel=r=>b(this._hass)[os[r.name]]??r.name,e.addEventListener("value-changed",r=>this._report(r.detail.value)),this.shadowRoot.append(e)),e.hass=this._hass,e.data=this._config,e.schema=this._schema()}_schema(){return[{name:"title",selector:{text:{}}},{name:"collection_key",selector:{text:{}}},{name:"devices",selector:{select:{multiple:!0,mode:"list",options:y(this._hass).map(e=>({value:e.key,label:e.name}))}}},...this._extraSchema()]}_report(e){this.dispatchEvent(new CustomEvent("config-changed",{detail:{config:ns({...this._config,...e})},bubbles:!0,composed:!0}))}},ns=t=>Object.fromEntries(Object.entries(t).filter(([,e])=>e!==""&&e!==void 0&&e!==null&&!(Array.isArray(e)&&e.length===0))),_=(t,e)=>{customElements.get(t)||customElements.define(t,e)};var w=class extends F{static chartTag="ha-chart-base";static bearingCard={type:"statistics-graph",entities:[]};static emptyKey="no_cost_in_period";static chartHeight="clamp(320px, 40vw, 480px)";static cardStyle=`
    ha-chart-base { display: block; --chart-max-height: none; }
  `;constructor(){super(),this._chartReady=!!customElements.get(this.constructor.chartTag)}getCardSize(){return 6}static narrowQuery="";connectedCallback(){super.connectedCallback(),this._chartReady||this._loadChartComponent(),this._watchScreen()}disconnectedCallback(){super.disconnectedCallback(),this._screen?.removeEventListener?.("change",this._onScreenChange),this._screen=null}_watchScreen(){let{narrowQuery:e}=this.constructor;!e||this._screen||(this._screen=globalThis.matchMedia?.(e),this._onScreenChange??=()=>this._render(),this._screen?.addEventListener?.("change",this._onScreenChange))}async _loadChartComponent(){let{chartTag:e,bearingCard:r}=this.constructor;customElements.whenDefined(e).then(()=>{this._chartReady=!0,this._render()});try{await(await globalThis.loadCardHelpers?.())?.createCardElement(r)}catch(s){console.warn(`${e}: could not be loaded`,s)}}_isEmpty(){return(this._result?.series??[]).length===0}_body(){return this._chartReady?this._isEmpty()?`<p class="message">${this._labels[this._emptyKey()]}</p>`:this._chartMarkup():`<p class="message">${this._labels.chart_not_loaded}</p>`}_emptyKey(){return this.constructor.emptyKey}_chartMarkup(){return'<ha-chart-base chart-type="bar"></ha-chart-base>'}_afterRender(){let e=this.shadowRoot.querySelector(this.constructor.chartTag);e&&(e.hass=this._hass,this._draw(e))}_chartHeight(){return this.constructor.chartHeight}_draw(e){e.height=this._chartHeight(),e.data=this._series(),e.options=this._options(this._chartLocale())}_chartLocale(){return ne(this._hass)}_colour({variable:e,fallback:r}){return getComputedStyle(this).getPropertyValue(e).trim()||r}};var as=/^#([\da-f]{3}|[\da-f]{6})$/i,is=/^rgba?\(([^)]+)\)$/i,ke=t=>{let e=as.exec(String(t).trim());if(e){let o=e[1];return(o.length===3?[...o].map(n=>n+n):[0,2,4].map(n=>o.slice(n,n+2))).map(n=>Number.parseInt(n,16))}let r=is.exec(String(t).trim());if(!r)return;let s=r[1].split(/[\s,/]+/).filter(Boolean).slice(0,3).map(Number);return s.length===3&&s.every(Number.isFinite)?s:void 0},S=(t,e)=>{let r=ke(String(t).trim());return r?`rgba(${r.join(", ")}, ${e})`:t},cs=([t,e,r])=>(.2126*t+.7152*e+.0722*r)/255,ae=t=>{let e=ke(ls(t));return e?cs(e)>.5:!1},ls=t=>{let e=[t,t?.ownerDocument?.documentElement].filter(Boolean);for(let r of e){let s=getComputedStyle(r),o=s.getPropertyValue("--primary-text-color").trim()||s.color;if(ke(o))return o}return""};var St=Object.freeze({variable:"--primary-color",fallback:"#03a9f4"}),Tt=Object.freeze({variable:"--success-color",fallback:"#4caf50"}),ds=Object.freeze({paid:"paid",would_have_paid:"would-have-paid",saved:"saved"}),ie=`
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
`,ce=t=>{let e=typeof t=="string"?ds[t]:void 0;return e?`<span class="swatch ${e}" aria-hidden="true"></span>`:""};var $=(t,e,r,{bold:s=!1}={})=>{let o=document.createElement("div");o.style.display="flex",o.style.justifyContent="space-between",o.style.gap="16px",s&&(o.style.fontWeight="bold");let a=document.createElement("span");a.textContent=t;let n=document.createElement("span");return n.textContent=e,n.style.fontVariantNumeric="tabular-nums",r&&(n.style.color=r),o.append(a,n),o},us=t=>{let e=document.createElement("span");return e.style.display="inline-block",e.style.width="10px",e.style.height="10px",e.style.borderRadius="10px",e.style.marginInlineEnd="4px",e.style.verticalAlign="middle",e.style.backgroundColor=t,e},At=(t,e,r,s)=>{let o=$(e,r,s);return o.firstChild.prepend(us(t)),o},le=t=>{let e=document.createElement("div");return e.textContent=t,e.style.fontWeight="bold",e.style.textAlign="center",e.style.marginBottom="4px",e},Ot=t=>{let e=document.createElement("div");return e.textContent=t,e.style.marginTop="4px",e.style.maxWidth="260px",e.style.whiteSpace="normal",e.style.opacity="0.7",e};var Rt="hea-cost-over-time-card",It=`${Rt}-editor`,hs={hour:3600*1e3,day:1440*60*1e3},ms=50,ps=.5,fs=(t,e)=>{if(!t.length||!e)return 0;let r=hs[C(e)]??0,s=t.length>=2?t[1].start.getTime()-t[0].start.getTime():void 0;return(s?Math.min(s,r):r)/2},R={paid:{id:"paid",name:"paid",...St},saved:{id:"saved",name:"saved",...Tt}},Nt={variable:"--error-color",fallback:"#db4437"},_s={gain:{variable:"--success-color",fallback:"#4caf50"},loss:Nt},Se=t=>t.value?.[1]??0,gs=t=>t.value?.[2],ys=.45,de={id:"before",name:"compared_series",variable:"--secondary-text-color",fallback:"#727272"},Te=class extends w{static titleKey="title_cost_over_time";static getConfigElement(){return document.createElement(It)}_series(){let e=xt(this._result?.series??[],this._result?.period),r=this._colour(Nt),s=this._labels,o=this._result?.seriesBefore,a=fs(e,this._result?.period);return[...te([{...$t(R.paid,this._colour(R.paid),s),data:e.map(n=>Ct(n,Ft(n,n.actualCost,a)))},{...$t(R.saved,this._colour(R.saved),s),data:e.map(n=>{let i=Ft(n,n.costSavings,a),c=n.costSavings<0?Dt(r):void 0;return Ct(n,i,c)})}]),...o?.length?[{id:de.id,name:s[de.name],type:"line",symbol:"none",lineStyle:{type:"dashed",width:2},itemStyle:{color:this._colour(de)},data:o.map(n=>[n.start.getTime()+a,n.costAtGridPrice])}]:[]]}_caption(e){return`${super._caption(e)}${this._stillAccruingNote()}`+this._accrualNote()}_stillAccruingNote(){return(this._result?.series??[]).some(e=>e.accruing)?`<div class="hint">${this._labels.still_accruing}</div>`:""}_accrualNote(){return this._devices().length!==1||!this._period||C(this._period)!=="hour"?"":`<div class="hint">${this._labels.hourly_shape_estimate}</div>`}_tooltipFor(e,r){let s=(Array.isArray(e)?e:[e]).filter(c=>c.componentSubType==="bar"),o=s.filter(c=>Se(c)!==0);if(!o.length)return;let a=this._bucketAt(s.map(gs).find(c=>c!==void 0)),n=document.createElement("div");n.append(le(this._spanOf(a,r)));for(let c of o)n.append(this._tooltipRowFor(c,r));let i=s.reduce((c,l)=>c+Se(l),0);return o.length>1&&n.append($(this._labels.would_have_paid,u(i,r),void 0,{bold:!0})),a?.accruing&&n.append(Ot(this._labels.still_accruing)),n}_tooltipRowFor(e,r){let s=Se(e),a=e.seriesId===R.saved.id&&s<0?this._labels.lost:e.seriesName,n=e.seriesId===R.saved.id?T(s):"";return At(e.color,a,u(s,r),n?this._colour(_s[n]):void 0)}_bucketAt(e){if(e!==void 0)return(this._result?.series??[]).find(r=>r.start.getTime()===e)}_spanOf(e,r){return!e||!this._period?"":at(e.start,C(this._period),r)}_headerChip(e){let r=this._result?.totals?.actualCost;return Number.isFinite(r)&&!this._isEmpty()?u(r,e):""}_axisBounds(){if(!this._period)return{};let{start:e,end:r}=this._period,s=new Date(r.getTime()-1);return C(this._period)==="hour"?s.setMinutes(30,0,0):(s.getHours()===0&&s.setHours(s.getHours()-1),s.setHours(0,0,0,0)),{min:e.getTime(),max:s.getTime()}}_options(e){let r=this._labels;return{xAxis:{type:"time",...this._axisBounds()},grid:{top:15,bottom:0,left:1,right:1,containLabel:!0},yAxis:{type:"value",name:K(e),nameGap:2,nameTextStyle:{align:"left"},boundaryGap:[0,0],splitNumber:5,splitLine:{show:!0},axisLabel:{formatter:s=>z(s,e),hideOverlap:!0}},tooltip:{trigger:"axis",axisPointer:{type:"shadow"},formatter:s=>this._tooltipFor(s,e)},legend:{show:!0,type:"custom",data:[R.paid,R.saved,...this._result?.seriesBefore?.length?[de]:[]].map(s=>({id:s.id,name:r[s.name],itemStyle:{color:this._colour(s)}}))}}}},Ct=(t,e,r=void 0)=>t.accruing?{value:e,itemStyle:{...r,opacity:ys}}:r?{value:e,itemStyle:r}:e,Ft=(t,e,r)=>[t.start.getTime()+r,e,t.start.getTime()],$t=({id:t,name:e},r,s)=>({id:t,name:s[e],type:"bar",stack:"cost",barMaxWidth:ms,itemStyle:Dt(r)}),Dt=t=>({color:S(t,ps),borderColor:t,borderWidth:1}),Ae=class extends m{},bs=()=>{_(It,Ae),f(Rt,Te,{name:"Home Energy Advisor: Cost over time",description:"What the period cost, stacked against what it would have cost at grid price."})};bs();var Fe="hea",Ht="Home Energy Advisor",vs="mdi:home-lightning-bolt",Lt=`ll-strategy-dashboard-${Fe}`,Mt=`ll-strategy-view-${Fe}`,xs=[{type:"custom:hea-totals-card"},{type:"custom:hea-devices-card",sort_by:"actual_cost"},{type:"custom:hea-cost-over-time-card"},{type:"custom:hea-sources-card",sort_by:"energy_used"}],ws=[{type:"custom:hea-device-costs-card"},{type:"custom:hea-distribution-card"},{type:"custom:hea-self-sufficiency-card"}],Es=t=>({...t,grid_options:{columns:"full",rows:"auto"}}),Gt=t=>({type:"grid",column_span:2,cards:t.map(Es)}),ks=()=>({card:{type:"horizontal-stack",cards:[{type:"energy-date-selection",vertical_opening_direction:"up"},{type:"custom:hea-filter-card"}]},max_width:1600}),Ss=t=>({type:"sections",max_columns:4,sections:[{type:"grid",cards:[{type:"markdown",content:b(t).no_devices}]}]}),Ts=t=>y(t).length===0?Ss(t):{type:"sections",max_columns:4,sections:[Gt(xs),Gt(ws)],footer:ks()},Pt=async t=>(await A(t),Ts(t)),Oe=class extends HTMLElement{static async generate(e,r){return{views:[await Pt(r)]}}static noEditor=!0;static getCreateSuggestions(){return{title:Ht,icon:vs}}},Ce=class extends HTMLElement{static async generate(e,r){return Pt(r)}},As=t=>{globalThis.customStrategies=globalThis.customStrategies??[],globalThis.customStrategies.some(e=>e.type===t.type)||globalThis.customStrategies.push(t)},Os=()=>{customElements.get(Lt)||customElements.define(Lt,Oe),customElements.get(Mt)||customElements.define(Mt,Ce),As({type:Fe,strategyType:"dashboard",name:Ht,description:"What each device cost to run, and what solar and the battery saved."})};Os();var jt=Object.keys(P),Cs=Object.keys(O),Ut=t=>{let e=new Map;for(let r of t){if(!r.upstream)continue;let s=e.get(r.upstream);s?s.push(r):e.set(r.upstream,[r])}return e},Bt=(t,e)=>({...t,key:`${t.key}${Fs}`,name:`${t.name} ${e.device_untracked}`,upstream:t.key,untracked:!1,residualOf:t.key}),Fs="__untracked",$s=t=>{let e=Object.fromEntries(jt.map(r=>[r,0]));for(let r of t)for(let s of jt)e[s]+=r[s]??0;for(let r of Cs)e[r]=t.every(s=>typeof s[r]=="number")?t.reduce((s,o)=>s+o[r],0):void 0;return e.costSavings=e.costAtGridPrice-e.actualCost,e},ue=(t,e)=>{let r=Ut(t);return r.size===0?t:t.flatMap(s=>r.has(s.key)?[Bt(s,e)]:[s])},Wt=(t,e,r=s=>s)=>{let s=Ut(t);if(s.size===0)return r(t).map(n=>({device:n,depth:0}));let o=new Set(s.keys()),a=t.filter(n=>!n.upstream);return r(a).flatMap(n=>{if(!o.has(n.key))return[{device:n,depth:0}];let i=r([...s.get(n.key),Bt(n,e)]);return[{device:{...n,...$s(i),subtotal:!0},depth:0},...i.map(c=>({device:c,depth:1}))]})};var E=Object.freeze(["#0072b2","#e69f00","#009e73","#cc79a7","#56b4e9","#d55e00","#8c6bb1","#3d9970"]),Rs=Object.freeze(["#4b46b3","#8d9b1f","#00a2ab","#b07ad2","#7fa0ee","#a8761b","#b26596","#5b8f3f"]),$e=Object.freeze([E,Rs]),vn=E.length*$e.length,j=Object.freeze({variable:"--secondary-text-color",fallback:"#8a8a8a"}),U=t=>{let e=(t??[]).filter(r=>!r.untracked).map(r=>r.key).sort(Is);return new Map(e.map((r,s)=>{let o=Math.floor(s/E.length)%$e.length;return[r,$e[o][s%E.length]]}))},Is=(t,e)=>t===e?0:t<e?-1:1;var he=(t,e,r)=>{let s=t<0?e.lost_share:e.saved_share;return v(s,{percent:H(Math.abs(t),r)})},Ns=({costSavings:t,costAtGridPrice:e})=>{if(!(!Number.isFinite(t)||!Number.isFinite(e))&&!(e<=0))return t/e},q=[{at:0,hue:3,light:48,dark:62},{at:.5,hue:35,light:46,dark:68},{at:1,hue:142,light:31,dark:76}],zt={light:85,dark:70},Ds=.7,Kt=(t,e,r)=>t+(e-t)*r,Ls=.6,Ms=(t,e)=>{let r=q.findIndex(i=>t<=i.at);if(r<=0)return{hue:q[0].hue,lightness:q[0][e]};let s=q[r-1],o=q[r],a=(t-s.at)/(o.at-s.at),n=r===1?a:a**Ls;return{hue:Kt(s.hue,o.hue,n),lightness:Kt(s[e],o[e],a)}},Yt=.05,I=t=>Math.round(t*10)/10,me=(t,{dark:e=!1}={})=>{let r=e?"dark":"light",s=a=>Math.max(0,a?.costAtGridPrice??0),o=Math.max(0,...(t??[]).map(s));return a=>{let n=Ns(a??{});if(n===void 0||o<=0)return;let i=Math.min(1,s(a)/o),c=i*(1+Yt)/(i+Yt),l=Math.min(1,Math.max(0,n)),{hue:d,lightness:p}=Ms(l,r),x=zt[r]*c**Ds;return{rate:n,text:`hsl(${I(d)}, ${I(x)}%, ${I(p)}%)`,edge:`hsla(${I(d)}, ${I(zt[r])}%, ${I(p)}%, ${I(c)})`}}};var tr="hea-device-costs-card",rr=`${tr}-editor`,Vt={variable:"--error-color",fallback:"#db4437"},Gs={variable:"--secondary-text-color",fallback:"#727272"},Hs="earlier-period",Ps=["auto","vertical","horizontal"],qt="(max-width: 767px)",js="paid",Us="saved",Zt="before",Bs=30,Ws=46,zs=64,Ks=240,Ys=24,Vs=12,qs=2,Zs=10,Xs=300,Qs=120,Js="40vw",eo={left:8,right:16,top:8,bottom:28,containLabel:!0},Xt=1.5,Qt=.8,Jt=.45,er=.22,to=/:(?:paid|saved|before)$/,ro={gain:{variable:"--success-color",fallback:"#4caf50"},loss:{variable:"--error-color",fallback:"#db4437"}},so=(t,e,r,s,o,a)=>{let n=T(t.costSavings),i=document.createElement("div");i.append(le(e),$(s.paid,u(t.actualCost,r)),$(t.costSavings<0?s.lost:s.saved,u(t.costSavings,r),n?o(n):void 0),$(s.would_have_paid,u(t.costAtGridPrice,r)));let c=oo(a,r,s);c&&i.append(c);let l=no(t,r,s,o);l&&i.append(l);let d=ao(t,r,s);return d&&i.append(d),i},oo=(t,e,r)=>{if(!t)return;let s=document.createElement("div");return s.style.marginTop="4px",s.style.color=t.text,s.textContent=he(t.rate,r,e),s},no=(t,e,r,s)=>{let o=t.before?.actualCost;if(!Number.isFinite(o)||!Number.isFinite(t.actualCost))return;let a=t.actualCost-o,n=M("actualCost",a);return $(r.change,v(r.compared,{change:L(a,e),before:u(o,e)}),n?s(n):void 0)},ao=({costFloor:t,costCeiling:e},r,s)=>{if(![t,e].every(a=>Number.isFinite(a)))return;let o=document.createElement("div");return o.style.marginTop="4px",o.style.opacity="0.75",o.textContent=v(s.range_device,{range:G([t,e],r)}),o},Re=class extends w{static titleKey="title_device_costs";static narrowQuery=qt;static getConfigElement(){return document.createElement(rr)}_isEmpty(){return this._ranked().every(e=>!e.costAtGridPrice&&!e.actualCost)}_ranked(){return ue(this._result?.devices??[],this._labels).sort((e,r)=>r.actualCost-e.actualCost||e.name.localeCompare(r.name))}_colourFor(e){if(e.untracked)return this._colour(j);let r=e.residualOf??e.key;return this._colours().get(r)??E[0]}_colours(){return U(y(this._hass))}_verdicts(){return me(this._ranked(),{dark:ae(this)})}_sideways(){let e=this._config?.layout;return e==="horizontal"?!0:e==="vertical"?!1:!!globalThis.matchMedia?.(qt)?.matches}_comparing(){return this._ranked().some(e=>e.before)}_series(){return te(this._sideways()?this._sidewaysSeries():this._standingSeries())}_sidewaysSeries(){let e=this._ranked(),r=this._colour(Vt),s=this._labels,o=a=>this._colourFor(a);return[{id:js,name:s.paid,type:"bar",stack:"cost",data:e.map(a=>({value:a.actualCost,itemStyle:{color:S(o(a),Qt)}}))},{id:Us,name:s.saved,type:"bar",stack:"cost",data:e.map(a=>{let n=a.costSavings<0?r:o(a);return{value:a.costSavings,itemStyle:{color:S(n,er),borderColor:n,borderWidth:Xt}}})},...this._comparing()?[{id:Zt,name:s.compared_series,type:"bar",stack:"earlier",data:e.map(a=>({value:a.before?a.before.actualCost:null,itemStyle:{color:S(o(a),Jt)}}))}]:[]]}_standingSeries(){let e=this._colour(Vt);return this._ranked().flatMap(r=>{let s=this._colourFor(r),o=r.costSavings<0?e:s,a=r.name;return[{id:`${r.key}:paid`,name:a,type:"bar",stack:r.key,itemStyle:{color:S(s,Qt)},data:[r.actualCost]},{id:`${r.key}:saved`,name:a,type:"bar",stack:r.key,itemStyle:{color:S(o,er),borderColor:o,borderWidth:Xt},data:[r.costSavings]},...r.before?[{id:`${r.key}:before`,name:a,type:"bar",stack:`${r.key}:before`,itemStyle:{color:S(s,Jt)},data:[r.before.actualCost]}]:[]]})}_tooltipFor({seriesId:e,dataIndex:r},s){let o=this._ranked(),a=this._sideways()?o[r]:o.find(n=>n.key===String(e??"").replace(to,""));return a?so(a,a.name,s,this._labels,n=>this._colour(ro[n]),this._verdicts()(a)):void 0}_earlierKey(){if(!this._comparing())return[];let e=this._labels.compared_series,r={color:this._colour(Gs)};return this._sideways()?[{id:Zt,name:e,itemStyle:r}]:[{id:Hs,secondaryIds:this._ranked().filter(s=>s.before).map(s=>`${s.key}:before`),name:e,itemStyle:r}]}_chartHeight(){if(this._sideways()){let r=this._ranked().length,s=this._comparing()?Ws:Bs;return`${Math.max(Ks,zs+r*s)}px`}let e=Xs+this._legendHeight();return`clamp(${e}px, ${Js}, ${e+Qs}px)`}_legendHeight(){let e=Math.min(this._ranked().length,Zs)+this._earlierKey().length;return Math.ceil(e/qs)*Ys+Vs}_options(e){return this._sideways()?this._sidewaysOptions(e):this._standingOptions(e)}_sidewaysOptions(e){let r=this._earlierKey();return{xAxis:{type:"value",name:K(e),axisLabel:{formatter:s=>z(s,e),hideOverlap:!0}},yAxis:{type:"category",data:this._ranked().map(s=>s.name),inverse:!0},grid:eo,tooltip:{trigger:"item",formatter:s=>this._tooltipFor(s,e)},...r.length?{legend:{show:!0,type:"custom",data:r}}:{}}}_standingOptions(e){return{xAxis:{type:"category",data:[Y(this._period,e)]},yAxis:{type:"value",name:K(e),nameGap:2,nameTextStyle:{align:"left"},axisLabel:{formatter:r=>z(r,e),hideOverlap:!0}},tooltip:{trigger:"item",formatter:r=>this._tooltipFor(r,e)},legend:{show:!0,type:"custom",data:[...this._ranked().map(r=>({id:`${r.key}:paid`,secondaryIds:[`${r.key}:saved`,...r.before?[`${r.key}:before`]:[]],name:r.name,itemStyle:{color:this._colourFor(r)}})),...this._earlierKey()]}}}},Ie=class extends m{_extraSchema(){return[{name:"layout",selector:{select:{mode:"dropdown",options:Ps}}}]}},io=()=>{_(rr,Ie),f(tr,Re,{name:"Home Energy Advisor: Device costs (chart)",description:"What each device cost over the selected period, dearest first."})};io();var co=`${ie}
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
    cursor: help;
    text-decoration: underline dotted
      var(--secondary-text-color, rgba(0, 0, 0, 0.54));
    text-underline-offset: 3px;
  }
  .revealed {
    display: none;
    margin-left: 0.5em;
    color: var(--secondary-text-color);
    font-size: 0.85em;
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
`,sr=(t,e,r)=>{let s=t==="costSavings"?T(r):M(e,r);return s?` class="${s}"`:""},or=t=>t?` style="box-shadow: inset ${lo} 0 0 ${t.edge}"`:"",lo="4px",N=class extends F{static columns=[];static sorts={};static defaultSort="";static cardStyle=co;setConfig(e){let{sorts:r}=this.constructor;if(e.sort_by!==void 0&&!(e.sort_by in r))throw new Error(`\`sort_by\` must be one of: ${Object.keys(r).join(", ")}`);super.setConfig(e)}getCardSize(){return 3+Math.ceil((this._result?.devices.length??3)/2)}_columns(){return this.constructor.columns}_body(e){let r=this._columns(),s=this._verdictScale();return`
      <div class="scroll">
        <table>
          <thead><tr>${r.map(o=>this._heading(o,e)).join("")}</tr></thead>
          <tbody>${this._ranked().map(({device:o,depth:a})=>this._row(o,e,s,a)).join("")}</tbody>
          <tfoot>${this._total(e,s)}</tfoot>
        </table>
      </div>`}_verdictScale(){if(this._columns().some(e=>e.carriesVerdict))return me(this._result?.devices??[],{dark:ae(this)})}_heading({label:e},r){let s=this._labels;if(typeof e!="function")return`<th>${ce(e)}${s[e]}</th>`;let{text:o,unit:a}=e(r,s);return`<th>${o} <span class="unit">${g(a)}</span></th>`}_rank(e){let{sorts:r,defaultSort:s}=this.constructor,{field:o}=r[this._config?.sort_by??s];return[...e].sort((a,n)=>n[o]-a[o]||a.name.localeCompare(n.name))}_ranked(){return Wt(this._result?.devices??[],this._labels,e=>this._rank(e))}_row(e,r,s,o){return`<tr${e.subtotal?' class="subtotal"':""}>${this._columns().map(n=>this._cell(n,e,r,s?.(e),o)).join("")}</tr>`}_cell({field:e,derive:r,format:s,tone:o,carriesVerdict:a,reveal:n},i,c,l,d){if(!s)return`<th scope="row"${d?' class="inside"':""}${or(l)}>${g(i.name)}</th>`;let p=r?r(i):i[e],x=a?this._verdictOn(l,c):"",ee=this._revealed(s(p,c),n?.(i,c));return`<td${sr(e,o,p)}${x}>${ee}</td>`}_revealed(e,r){return r?`<span class="reveal" tabindex="0" aria-label="${g(r.label)}">${e}<span class="revealed" aria-hidden="true">${g(r.text)}</span></span>`:e}_total(e,r){let s=this._sumOfShown(),o=r?.(s);return`<tr>${this._columns().map(({field:n,derive:i,format:c,tone:l,carriesVerdict:d})=>{if(!c)return`<th scope="row"${or(o)}>${this._labels.total}</th>`;let p=i?i(s):s[n],x=d?this._verdictOn(o,e):"";return`<td${sr(n,l,p)}${x}>${c(p,e)}</td>`}).join("")}</tr>`}_verdictOn(e,r){if(!e)return"";let s=he(e.rate,this._labels,r);return` style="color: ${e.text}" title="${g(s)}"`}_sumOfShown(){let e=[...new Set(this._columns().flatMap(({field:n,fields:i,derive:c,format:l})=>l?c?i??[]:n?[n]:[]:[]))],r=ue(this._result?.devices??[],this._labels),s=Object.fromEntries(this._columns().flatMap(({fields:n,field:i,readField:c})=>c?(n??[i]).map(l=>[l,c]):[])),o=n=>r.reduce((i,c)=>{for(let l of e){let d=n(c);i[l]+=s[l]?s[l](d,l):d[l]}return i},Object.fromEntries(e.map(i=>[i,0]))),a=o(n=>n);return r.length>0&&r.every(n=>n.before)&&(a.before=o(n=>n.before)),a}},pe=(t,e)=>[{name:"sort_by",selector:{select:{mode:"dropdown",options:Object.entries(t).map(([r,{label:s}])=>({value:r,label:e[s]}))}}}];var ar="hea-devices-card",ir=`${ar}-editor`,uo=({actualCost:t,energyUsed:e})=>e>0?t/e:void 0,cr=t=>Object.values(O).every(e=>e in(t.statistics??{})),Z={fields:["costFloor","costCeiling"],derive:({costFloor:t,costCeiling:e})=>[t,e],label:"range_column",format:G,readField:(t,e)=>Number.isFinite(t[e])?t[e]:t.actualCost},lr={fields:["actualCost"],derive:({actualCost:t,before:e})=>e&&Number.isFinite(t)&&Number.isFinite(e.actualCost)?t-e.actualCost:void 0,label:"change",format:L,tone:"actualCost"},Ne={field:"actualCost",label:"paid",format:u,reveal:(t,e)=>{if(!cr(t)||!Z.fields.every(s=>Number.isFinite(t[s])))return null;let r=G(Z.derive(t),e);return{text:r,label:`${u(t.actualCost,e)} (${r})`}}},nr=[{field:"name",label:"device"},{field:"energyUsed",label:"energy",format:k},Ne,lr,Z,{field:"costAtGridPrice",label:"would_have_paid",format:u,carriesVerdict:!0},{field:"costSavings",label:"saved",format:u},{derive:uo,label:(t,e)=>({text:e.rate,unit:lt(t)}),format:dt}],dr={actual_cost:{field:"actualCost",label:"paid"},cost_at_grid_price:{field:"costAtGridPrice",label:"would_have_paid"},cost_savings:{field:"costSavings",label:"saved"},energy_used:{field:"energyUsed",label:"energy_used"}},De=class extends N{static titleKey="title_devices";static columns=nr;static sorts=dr;static defaultSort="actual_cost";static cardStyle=`${N.cardStyle}
    .disclosure {
      margin-top: var(--hea-space-m);
      color: var(--secondary-text-color);
      font-size: 0.8em;
    }
  `;static getConfigElement(){return document.createElement(ir)}_columns(){let e=this._config?.range==="column"&&this._hasEveryBound(),r=new Set;return e||r.add(Z),this._hasComparison()||r.add(lr),nr.filter(s=>!r.has(s)).map(s=>s===Ne&&e?{...Ne,reveal:void 0}:s)}_hasComparison(){return(this._result?.devices??[]).some(e=>e.before)}_hasEveryBound(){let e=(this._result?.devices??[]).filter(cr);return e.length>0&&e.every(r=>Z.fields.every(s=>Number.isFinite(r[s])))}_body(e){return`${super._body(e)}${this._disclosure(e)}`}_disclosure(e){let r=this._labels;if(this._hasEveryBound())return`<div class="disclosure">${r.range_note}</div>`;let s=this._result?.wholeHome;if(!s)return"";let o=G([s.costFloor,s.costCeiling],e);return`<div class="disclosure">
      ${v(r.range_whole_home,{range:o})}
    </div>`}},Le=class extends m{_extraSchema(){let e=b(this._hass);return[...pe(dr,e),{name:"range",selector:{select:{mode:"dropdown",options:[{value:"rollover",label:e.editor_range_rollover},{value:"column",label:e.editor_range_column}]}}}]}},ho=()=>{_(ir,Le),f(ar,De,{name:"Home Energy Advisor: Devices",description:"Every tracked device over the selected period, ordered by what it cost."})};ho();var Q="household",X=Object.freeze({source:0,household:1,floor:2,area:3,device:4}),ur=Object.freeze({cost:{field:"actualCost",sources:null},energy:{field:"energyUsed",sources:[{id:"grid",field:"energyFromGrid",variable:"--energy-grid-consumption-color",fallback:"#488fc2"},{id:"generation",field:"energyFromGeneration",variable:"--energy-solar-color",fallback:"#ff9800"},{id:"battery",field:"energyFromBattery",variable:"--energy-battery-out-color",fallback:"#4db6ac"}]}}),mo=t=>{let e=U(t);return r=>r.untracked?j.fallback:e.get(r.key)??E[0]},po=({fallback:t})=>t,pr=(t,e,{metric:r="cost",colour:s=po,deviceColour:o=mo(t)}={})=>{let{field:a,sources:n}=ur[r]??ur.cost,i=t.filter(h=>h[a]>0);if(i.length===0)return{nodes:[],links:[]};let c=new Map,l=new Map,d=[],p=[],x=0;i.forEach(h=>{let B=h[a];x+=B;let Ye=h.floorId?hr(c,h.floorId,h.floorName):null,fe=h.areaId?hr(l,h.areaId,h.areaName):null;Ye&&(Ye.value+=B),fe&&(fe.value+=B,fe.floorId??=h.floorId??null);let Ve=`device_${h.key}`;d.push({id:Ve,label:h.name,value:B,index:X.device,color:o(h),...go(h)}),p.push({source:_o(h),target:Ve,value:B})});let ee=fo(n,i,e,s);return{nodes:[...ee,{id:Q,label:e.household,value:x,index:X.household},...mr(c,"floor_",X.floor),...mr(l,"area_",X.area),...d],links:[...ee.map(h=>({source:h.id,target:Q,value:h.value})),...yo(c,l),...p]}},fo=(t,e,r,s)=>(t??[]).map(o=>({id:`source_${o.id}`,label:r[o.id],value:e.reduce((a,n)=>a+(n[o.field]??0),0),index:X.source,color:s(o)})).filter(o=>o.value>0),hr=(t,e,r)=>(t.has(e)||t.set(e,{id:e,name:r||e,value:0}),t.get(e)),_o=t=>t.areaId?`area_${t.areaId}`:t.floorId?`floor_${t.floorId}`:Q,go=t=>{let e=t.statistics?.actual_cost;return e?{entityId:e}:{}},mr=(t,e,r)=>[...t.values()].map(s=>({id:`${e}${s.id}`,label:s.name,value:s.value,index:r})),yo=(t,e)=>[...[...t.values()].map(r=>({source:Q,target:`floor_${r.id}`,value:r.value})),...[...e.values()].map(r=>({source:r.floorId?`floor_${r.floorId}`:Q,target:`area_${r.id}`,value:r.value}))];var _r="hea-distribution-card",gr=`${_r}-editor`,J={cost:{titleKey:"title_distribution",emptyKey:"no_cost_in_period",format:u},energy:{titleKey:"title_distribution_energy",emptyKey:"no_energy_in_period",format:k}},fr="(max-width: 767px)",bo="400px",vo=88,xo=240,wo=["auto","horizontal","vertical"],Me=class extends w{static titleKey="title_distribution";static chartTag="ha-sankey-chart";static bearingCard={type:"energy-sankey"};static narrowQuery=fr;static cardStyle=`
    ha-sankey-chart { display: block; min-height: 240px; }
  `;static getConfigElement(){return document.createElement(gr)}_isEmpty(){return this._layout().nodes.length===0}_verticalHeight({nodes:e}){let r=new Set(e.map(s=>s.index)).size;return`${Math.max(xo,r*vo)}px`}_metric(){return J[this._config?.metric]?this._config.metric:"cost"}_titleKey(){return J[this._metric()].titleKey}_emptyKey(){return J[this._metric()].emptyKey}_layout(){let e=U(y(this._hass));return pr(this._result?.devices??[],this._labels,{metric:this._metric(),colour:r=>this._colour(r),deviceColour:r=>r.untracked?this._colour(j):e.get(r.key)??E[0]})}_chartMarkup(){return"<ha-sankey-chart></ha-sankey-chart>"}_draw(e){e.data=this._layout(),e.vertical=this._isVertical(),e.style.height=this._isVertical()?this._verticalHeight(e.data):bo;let r=this._chartLocale(),{format:s}=J[this._metric()];e.valueFormatter=o=>s(o,r),this.toggleAttribute("data-vertical",e.vertical)}_isVertical(){let e=this._config?.layout;return e==="vertical"?!0:e==="horizontal"?!1:!!globalThis.matchMedia?.(fr)?.matches}},Ge=class extends m{_extraSchema(){return[{name:"metric",selector:{select:{mode:"dropdown",options:Object.keys(J)}}},{name:"layout",selector:{select:{mode:"dropdown",options:wo}}}]}},Eo=()=>{_(gr,Ge),f(_r,Me,{name:"Home Energy Advisor: Cost distribution",description:"Where the period's cost went, by floor, room and device."})};Eo();var yr="hea-filter-card",br=`${yr}-editor`,ko=[{kind:"area",label:"filter_rooms",id:"areaId",name:"areaName"},{kind:"floor",label:"filter_floors",id:"floorId",name:"floorName"}],D=({kind:t,id:e})=>`${t}:${e??""}`,So=t=>{let[e,r]=[t.slice(0,t.indexOf(":")),t.slice(t.indexOf(":")+1)];return{kind:e,id:r===""?null:r}},He=class extends HTMLElement{constructor(){super(),this.attachShadow({mode:"open"})}setConfig(e){this._config=e,this._render()}set hass(e){this._hass=e,A(e).then(()=>this._renderIfChanged()),this._renderIfChanged()}getCardSize(){return 1}static getConfigElement(){return document.createElement(br)}connectedCallback(){this._render(),this._unfilter??=oe(this._config?.collection_key,()=>this._renderIfChanged())}_signature(){return JSON.stringify([this._allDevices().map(e=>[e.key,e.name,e.areaId,e.areaName,e.floorId,e.floorName,e.labels]),D(W(this._config?.collection_key)),this._labels.filter_rooms])}_renderIfChanged(){this._signature()!==this._drawn&&this._render()}disconnectedCallback(){this._unfilter?.(),this._unfilter=null}get _labels(){return b(this._hass)}_devices(){return y(this._hass).filter(e=>!e.untracked)}_allDevices(){return y(this._hass)}_optionsFor({kind:e,id:r,name:s},o){let a=new Map,n=!1;for(let c of o)c[r]?a.set(c[r],c[s]??c[r]):n=!0;let i=[...a.entries()].map(([c,l])=>({value:D({kind:e,id:c}),text:l})).sort((c,l)=>c.text.localeCompare(l.text));return n&&i.push({value:D({kind:e,id:null}),text:this._labels.filter_unfiled}),i}_labelOptions(e){let r=et(this._hass);return[...new Set(e.flatMap(o=>o.labels??[]))].map(o=>({value:D({kind:"label",id:o}),text:r[o]??o})).sort((o,a)=>o.text.localeCompare(a.text))}_deviceOptions(){return this._allDevices().map(e=>({value:D({kind:"device",id:e.key}),text:e.name})).sort((e,r)=>e.text.localeCompare(r.text))}_groups(){let e=this._devices(),r=ko.map(o=>({label:this._labels[o.label],options:this._optionsFor(o,e)})),s=this._labelOptions(e);return s.length&&r.push({label:this._labels.filter_labels,options:s}),r.push({label:this._labels.filter_devices,options:this._deviceOptions()}),r.filter(o=>o.options.length>0)}_render(){let e=this._labels,r=this._devices();this._drawn=this._signature();let s=r.length?this._control(e):`<p class="message">${e.no_devices}</p>`;this.shadowRoot.innerHTML=`
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
    `;let o=this.shadowRoot.querySelector("select");o&&(o.value=D(W(this._config?.collection_key)),o.addEventListener("change",()=>st(this._config?.collection_key,So(o.value))))}_control(e){let r=this._groups().map(s=>`<optgroup label="${g(s.label)}">${s.options.map(o=>`<option value="${g(o.value)}">${g(o.text)}</option>`).join("")}</optgroup>`).join("");return`<div class="body">
      <span class="label">${e.title_filter}</span>
      <select>
        <option value="${D({kind:"all",id:null})}">${g(e.filter_everything)}</option>
        ${r}
      </select>
    </div>`}},Pe=class extends m{},To=()=>{_(br,Pe),f(yr,He,{name:"Home Energy Advisor: Filter",description:"Narrow every Home Energy Advisor card on the page to a room, a floor, a label or one device."})};To();var xr="hea-self-sufficiency-card",wr=`${xr}-editor`,vr=["energyUsed","energyFromGrid","energyFromGeneration","energyFromBattery"],Ao={maximumFractionDigits:0},Oo=.005,je=class extends w{static titleKey="title_self_sufficiency";static chartTag="ha-gauge";static bearingCard={type:"energy-self-sufficiency-gauge"};static emptyKey="no_energy_in_period";static cardStyle=`
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
  `;static getConfigElement(){return document.createElement(wr)}getCardSize(){return 4}_isEmpty(){return this._totals().energyUsed<=0}_totals(){return(this._result?.devices??[]).reduce((e,r)=>{for(let s of vr)e[s]+=r[s];return e},Object.fromEntries(vr.map(e=>[e,0])))}_shares(){let e=this._totals(),r=e.energyUsed,s=i=>e[i]/r,o=s("energyFromGeneration"),a=s("energyFromBattery"),n=s("energyFromGrid");return{generation:o,battery:a,grid:n,unaccounted:Math.max(0,1-o-a-n)}}_body(e){let r=super._body(e);return!this._chartReady||this._isEmpty()?r:`${r}${this._breakdown(e)}`}_chartMarkup(){return`<ha-gauge></ha-gauge>
      <div class="headline">${this._labels.from_generation}</div>`}_breakdown(e){let{battery:r,grid:s,unaccounted:o}=this._shares();return`<div class="shares">${[{label:"from_battery",value:r},{label:"from_grid",value:s},{label:"unaccounted",value:o}].filter(({label:n,value:i})=>n!=="unaccounted"||i>Oo).map(({label:n,value:i})=>`
        <div class="share">
          <span class="label">${this._labels[n]}</span>
          <span class="value" data-share="${n}">${H(i,e)}</span>
        </div>`).join("")}</div>
      <div class="note">${this._labels.self_sufficiency_note}</div>`}_draw(e){e.min=0,e.max=100,e.value=this._shares().generation*100,e.label="%",e.formatOptions=Ao,e.locale=this._hass?.locale}},Ue=class extends m{},Co=()=>{_(wr,Ue),f(xr,je,{name:"Home Energy Advisor: Self-sufficiency",description:"What share of the selected period's energy came from the household's own generation."})};Co();var Er="hea-sources-card",kr=`${Er}-editor`,Fo=({energyFromGrid:t,energyUsed:e})=>e>0&&t>=0&&t<=e?t/e:void 0,$o=[{field:"name",label:"device"},{field:"energyUsed",label:"energy",format:k},{field:"energyFromGrid",label:"grid",format:k},{field:"energyFromGeneration",label:"generation",format:k},{field:"energyFromBattery",label:"battery",format:k},{derive:Fo,label:"from_grid",format:H}],Sr={energy_used:{field:"energyUsed",label:"energy_used"},energy_from_grid:{field:"energyFromGrid",label:"from_grid"},energy_from_generation:{field:"energyFromGeneration",label:"from_generation"},energy_from_battery:{field:"energyFromBattery",label:"from_battery"}},Be=class extends N{static titleKey="title_sources";static columns=$o;static sorts=Sr;static defaultSort="energy_used";static getConfigElement(){return document.createElement(kr)}},We=class extends m{_extraSchema(){return pe(Sr,b(this._hass))}},Ro=()=>{_(kr,We),f(Er,Be,{name:"Home Energy Advisor: Energy sources",description:"Grid, generation and battery behind each device's energy over the period."})};Ro();var Tr="hea-totals-card",Ar=`${Tr}-editor`,Io=[{key:"actualCost",label:"paid"},{key:"costAtGridPrice",label:"would_have_paid"},{key:"costSavings",label:"saved"}],ze=class extends F{static titleKey="title_totals";static cardStyle=`${ie}
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
  `;static getConfigElement(){return document.createElement(Ar)}getCardSize(){return 3}_body(e){let r=this._result?.totals;return`<div class="figures">${Io.map(({key:o,label:a})=>{let n=r?.[o],i=o==="costSavings"?T(n):"",c=i?` ${i}`:"";return`
        <div class="figure">
          <span class="label">${ce(a)}${this._labels[a]}</span>
          <span class="value${c}" data-figure="${o}">${u(n,e)}</span>
          ${this._comparedTo(o,n,e)}
        </div>`}).join("")}</div>`}_comparedTo(e,r,s){let o=this._result?.totals?.before?.[e];if(!Number.isFinite(o)||!Number.isFinite(r))return"";let a=M(e,r-o);return`<span class="${a?`compare ${a}`:"compare"}" data-compare="${e}">${v(this._labels.compared,{change:L(r-o,s),before:u(o,s)})}</span>`}},Ke=class extends m{},No=()=>{_(Ar,Ke),f(Tr,ze,{name:"Home Energy Advisor: Totals",description:"What the selected period cost, what it would have cost at grid price, and the difference."})};No();
