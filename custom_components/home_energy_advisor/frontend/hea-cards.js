var Fr=[4,4,0,0],$r=[0,0,4,4],qe=t=>t!==null&&typeof t=="object"&&!Array.isArray(t),Rr=t=>{let e=qe(t)?t.value:t;return Array.isArray(e)?e[1]:e},ge=(t,e)=>{let r=qe(t)?{...t}:{value:t};return{...r,itemStyle:{...r.itemStyle,...e}}},te=t=>{let e=Math.max(...t.map(({data:o})=>o.length),0),r=t.map(({data:o})=>[...o]);for(let o of Ir(t))for(let s=0;s<e;s++)Nr(r,s,o);return t.map((o,s)=>({...o,data:r[s]}))},Ir=t=>{let e=new Map;return t.forEach((r,o)=>{let s=r.stack??Symbol(o),a=e.get(s);a?a.push(o):e.set(s,[o])}),[...e.values()]},Nr=(t,e,r)=>{let o=!1,s=!1;for(let a=r.length-1;a>=0;a--){let n=r[a],i=t[n][e];if(i===void 0)continue;let c=Rr(i);c?c>0&&!o?(t[n][e]=ge(i,{borderRadius:Fr}),o=!0):c<0&&!s&&(t[n][e]=ge(i,{borderRadius:$r}),s=!0):t[n][e]=ge(i,{borderWidth:0})}};var Ze="_energy",ye="energy_";var Dr=(t,e)=>{let r=t||(e?`${ye}${e}`:"");return r?r.startsWith(ye)?`_${r}`:`_${ye}${r}`:Ze},Mr=(t,e)=>typeof t=="string"&&t.startsWith(Ze)&&e!==null&&typeof e=="object"&&typeof e.subscribe=="function"&&"start"in e,Lr=(t=new Date)=>{let e=new Date(t);return e.setDate(e.getDate()-30),e.setHours(0,0,0,0),{start:e,end:t,fallback:!0}},Gr=t=>{let e=t?.connection;if(!e)return{};let r={};for(let o of Object.keys(e)){let s;try{s=e[o]}catch{continue}Mr(o,s)&&(r[o]=s)}return r},Hr=(t,e)=>{let r=Gr(t),o=Dr(e,t?.panelUrl);if(r[o])return r[o];let[s]=Object.values(r);return s??null},Pr=t=>t?.startCompare&&t?.endCompare?{compare:{start:t.startCompare,end:t.endCompare,mode:t.compareMode}}:{},Xe=(t,e,r)=>{let o=null,s=null,a=0,n=t,i=l=>{if(o)return!0;let d=Hr(l,e);if(!d)return!1;let h=v=>r({start:d.start,end:d.end,fallback:!1,...Pr(v)});return o=d.subscribe(h),h(),!0},c=()=>{s=setTimeout(()=>{s=null,a+=1,!i(n)&&a<40&&c()},250)};return r(Lr()),i(t)||c(),{retry:l=>(l&&(n=l),i(n)),unsubscribe:()=>{s&&clearTimeout(s),s=null;try{typeof o=="function"&&o()}catch{}o=null}}};var re="sensor.home_energy_advisor_devices",jr="home_energy_advisor",oe=t=>{if(t?.states?.[re])return re;let e=t?.entities;if(!e)return re;for(let[r,o]of Object.entries(e))if(o?.platform===jr&&Array.isArray(t?.states?.[r]?.attributes?.devices))return r;return re},y=(t,e=void 0)=>{let r=t?.states?.[e??oe(t)]?.attributes?.devices;return Array.isArray(r)?r.filter(o=>o?.key).map(tt):[]},Qe=(t,e=void 0)=>{let r=t?.states?.[e??oe(t)]?.attributes?.whole_home;return r?.key?tt(r):null},Je=(t,e=void 0)=>{let r=t?.states?.[e??oe(t)]?.attributes?.settled_until;if(typeof r!="string")return null;let o=new Date(r);return Number.isNaN(o.getTime())?null:o},et=(t,e=void 0)=>{let r=t?.states?.[e??oe(t)]?.attributes?.labels;return r&&typeof r=="object"?r:{}},tt=t=>({key:t.key,name:t.name||t.key,deviceId:t.device_id??null,untracked:!!t.untracked,statistics:t.statistics??{},areaId:t.area_id??null,areaName:t.area_name??null,floorId:t.floor_id??null,floorName:t.floor_name??null,upstream:t.upstream??null,labels:Array.isArray(t.labels)?t.labels:[]});var rt=Object.freeze({kind:"all",id:null}),Ur={area:"areaId",floor:"floorId"},be=new Map,ve=t=>(be.has(t)||be.set(t,{filter:rt,listeners:new Set}),be.get(t)),Y=t=>ve(t).filter,se=(t,e)=>{let{listeners:r}=ve(t);return r.add(e),()=>r.delete(e)},ot=(t,e)=>{let r=ve(t),o={kind:e?.kind??"all",id:e?.id??null};if(!(o.kind===r.filter.kind&&o.id===r.filter.id)){r.filter=o;for(let s of r.listeners)try{s(o)}catch(a){console.warn("home-energy-advisor: a card could not follow the filter",a)}}},st=(t,e)=>{let{kind:r,id:o}=e??rt;if(r==="all")return!0;if(r==="device")return t.key===o;if(t.untracked)return!1;if(r==="label")return(t.labels??[]).includes(o);let s=Ur[r];return s?(t[s]??null)===o:!0};var Br={day:"numeric",month:"short",year:"numeric"},ne=t=>({language:t?.locale?.language||void 0,currency:t?.config?.currency||void 0,timeFormat:t?.locale?.time_format||void 0,timeZone:t?.locale?.time_zone==="server"?t?.config?.time_zone:void 0}),zr=({timeFormat:t,language:e})=>{if(t==="language"||t==="system"||!t){let r=t==="system"?void 0:e;return new Date("January 1, 2023 22:00:00").toLocaleString(r).includes("10")}return t==="12"},nt=(t,e)=>new Intl.DateTimeFormat(e.language,{hour:"numeric",minute:"2-digit",hourCycle:zr(e)?"h12":"h23",timeZone:e.timeZone}).format(t),Wr=(t,e)=>new Intl.DateTimeFormat(e.language,{weekday:"short",month:"short",day:"numeric",timeZone:e.timeZone}).format(t),Kr={hour:3600*1e3},at=(t,e,r)=>{let o=Kr[e];if(!o)return Wr(t,r);let s=new Date(t.getTime()+o);return`${nt(t,r)} \u2013 ${nt(s,r)}`},u=(t,{language:e,currency:r})=>{if(typeof t!="number"||!Number.isFinite(t))return"-";let o=r?{style:"currency",currency:r}:{minimumFractionDigits:2,maximumFractionDigits:2};return new Intl.NumberFormat(e,o).format(t)},P=(t,{language:e,currency:r})=>{if(typeof t!="number"||!Number.isFinite(t))return"-";let o=r?{style:"currency",currency:r,signDisplay:"exceptZero"}:{minimumFractionDigits:2,maximumFractionDigits:2,signDisplay:"exceptZero"};return new Intl.NumberFormat(e,o).format(t)},Yr=new Set(["actualCost","costAtGridPrice","energyUsed"]),Vr=new Set(["costSavings"]),T=t=>typeof t!="number"||!Number.isFinite(t)||t===0?"":t>0?"gain":"loss",j=(t,e)=>typeof e!="number"||!Number.isFinite(e)||e===0?"":Yr.has(t)?e<0?"gain":"loss":Vr.has(t)?e>0?"gain":"loss":"",N=(t,e)=>{if(!Array.isArray(t))return"-";let[r,o]=t;if(![r,o].every(n=>Number.isFinite(n)))return"-";if(r===o)return u(r,e);let[s,a]=r<=o?[r,o]:[o,r];return`${u(s,e)} - ${u(a,e)}`},k=(t,{language:e})=>typeof t!="number"||!Number.isFinite(t)?"-":`${new Intl.NumberFormat(e,{maximumFractionDigits:1}).format(t)} kWh`,it={EUR:{symbol:"c",per:100},USD:{symbol:"\xA2",per:100},GBP:{symbol:"p",per:100}},V=(t,{language:e})=>typeof t!="number"||!Number.isFinite(t)?"-":new Intl.NumberFormat(e,{minimumFractionDigits:t===0?0:2,maximumFractionDigits:2}).format(t),q=({language:t,currency:e})=>e?ct(t,e):"",ct=(t,e)=>new Intl.NumberFormat(t,{style:"currency",currency:e}).formatToParts(0).find(r=>r.type==="currency")?.value??"",lt=({language:t,currency:e})=>{if(!e)return"/kWh";let r=it[e];return`${r?r.symbol:ct(t,e)}/kWh`},dt=(t,{language:e,currency:r})=>{if(typeof t!="number"||!Number.isFinite(t))return"-";let o=r?it[r]:void 0;return new Intl.NumberFormat(e,{minimumFractionDigits:o?1:0,maximumFractionDigits:o?2:3}).format(o?t*o.per:t)},U=(t,{language:e})=>typeof t!="number"||!Number.isFinite(t)?"-":new Intl.NumberFormat(e,{style:"percent",maximumFractionDigits:0}).format(t),g=t=>String(t).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#39;"),Z=(t,{language:e})=>t?new Intl.DateTimeFormat(e,Br).formatRange(t.start,t.end):"";var ht="common",mt="home_energy_advisor",ut=`component.${mt}.${ht}.card_`,we=Object.freeze({paid:"Paid",would_have_paid:"Would have paid",saved:"Saved",lost:"Lost",paid_with_forgone:"Cost of use",range_column:"Paid (min-max)",range_note:"Paid (min-max) is the widest range these readings allow, not a typical error: a meter that reports every 30-90 minutes leaves the exact moment of use unknown.",range_whole_home:"What you paid could honestly sit between {range} - the widest these readings allow, not a typical error.",range_device:"What you paid could be between {range}.",range_note_rollover:"Hover over or tap a figure in Paid to see the range it could honestly have been. That range is the widest these readings allow, not a typical error: a meter that reports every 30-90 minutes leaves the exact moment of use unknown.",range_note_cost_of_use:"Hover over or tap a figure in Cost of use to see what it is made of: what you paid, with the range it could honestly have been, plus what your own generation could have earned by exporting instead, at your export rate at the time. That second part is not money you paid, but money you did not receive. The range covers only what you paid. It is the widest these readings allow, not a typical error: a meter that reports every 30-90 minutes leaves the exact moment of use unknown.",range_note_not_cost_of_use:"It ranges what you paid, not Cost of use, which is what you paid plus Forgone export.",forgone_column:"Forgone export",paid_breakdown:"Paid {paid} ({range}) + {forgone} your generation could have earned",paid_breakdown_unranged:"Paid {paid} + {forgone} your generation could have earned",compared:"{change} vs {before}",compared_period:"{period} vs {compared}",saved_share:"{percent} of what you would have paid was saved.",lost_share:"{percent} more was paid than the grid would have cost.",change:"Change",compared_series:"Earlier period",device:"Device",energy:"Energy",rate:"Rate",total:"Total",grid:"Grid",generation:"Generation",battery:"Battery",from_grid:"From the grid",from_generation:"From generation",from_battery:"From the battery",energy_used:"Energy used",unaccounted:"Unaccounted",self_sufficiency_note:"Battery energy is counted on its own: it was charged from generation or from the grid, and these readings cannot say which.",household:"Household",title_totals:"Cost summary",title_devices:"Cost by device",title_device_costs:"What each device cost",title_cost_over_time:"Cost over time",title_sources:"Where the energy came from",title_self_sufficiency:"Self-sufficiency",title_distribution:"Where the cost went",title_distribution_energy:"Where the energy went",no_devices:"No devices are being tracked yet.",no_devices_in_filter:"No tracked device matches what the page is showing.",title_filter:"Show",filter_everything:"Everything",filter_rooms:"Rooms",filter_floors:"Floors",filter_labels:"Labels",filter_devices:"Devices",filter_unfiled:"Not in one",device_untracked:"Untracked",hourly_shape_estimate:"One device's hourly shape is an estimate: each meter reading is spread across the hours it spanned, so cost may not land in the hour the energy was used.",still_accruing:"The last interval is still being counted, so its bar will grow. Figures are complete about twenty minutes behind the clock, which is how long meters are given to report.",statistics_failed:"Statistics could not be loaded.",no_picker:"Add an Energy date picker card to choose the range.",chart_not_loaded:"Home Assistant's chart component is not loaded. Adding any energy or statistics card to this dashboard will load it.",no_cost_in_period:"No cost recorded in this period.",no_energy_in_period:"No energy recorded in this period.",editor_title:"Title",editor_collection_key:"Energy period (collection key)",editor_devices:"Devices (all, if none are chosen)",editor_sort_by:"Order by",editor_layout:"Layout",editor_metric:"Measure by",editor_group_by_floor:"Group by floor",editor_group_by_area:"Group by area",editor_forgone:"Count what your own generation could have earned",editor_forgone_include:"Include it in the cost",editor_forgone_exclude:"Show only what you paid",editor_range:"Show the cost range as",editor_range_rollover:"A rollover on Paid",editor_range_column:"Its own column"}),xe=new Map,pt=new Map,ft=t=>t?.locale?.language||t?.language||"en",A=t=>{let e=ft(t);return xe.has(e)||xe.set(e,qr(t,e).then(r=>(pt.set(e,r),r))),xe.get(e)},qr=async(t,e)=>{try{let{resources:r}=await t.callWS({type:"frontend/get_translations",language:e,category:ht,integration:[mt]});return Object.freeze({...we,...Zr(r)})}catch(r){return console.warn("home-energy-advisor: falling back to English labels",r),we}},x=t=>pt.get(ft(t))??we,Zr=t=>Object.fromEntries(Object.entries(t??{}).filter(([e,r])=>e.startsWith(ut)&&r).map(([e,r])=>[e.slice(ut.length),r])),b=(t,e)=>Object.entries(e).reduce((r,[o,s])=>r.replaceAll(`{${o}}`,s),t);var B=Object.freeze({energyUsed:"energy_used",actualCost:"actual_cost",costAtGridPrice:"cost_at_grid_price",energyFromGrid:"energy_from_grid",energyFromGeneration:"energy_from_generation",energyFromBattery:"energy_from_battery",forgoneExport:"forgone_export"}),O=Object.freeze({costFloor:"lowest_possible_cost",costCeiling:"highest_possible_cost"}),Ee=()=>Object.fromEntries(Object.keys(B).map(t=>[t,0])),yt=1440*60*1e3,bt={hour:3600*1e3,day:yt},Xr=2,X=(t,e)=>t?.statistics?.[e],Qr=(t,e)=>{let r=t.flatMap(o=>[...Object.values(B),...Object.values(O)].map(s=>X(o,s)).filter(Boolean));return!e?.statistics||t.length===0?r:[...r,...Object.values(O).map(o=>X(e,o)).filter(Boolean)]},vt=(t,e)=>{if(!e)return t;let r=new Map(e.devices.map(o=>[o.key,o]));return{...t,totals:{...t.totals,before:e.totals},devices:t.devices.map(o=>({...o,before:r.get(o.key)})),seriesBefore:Jr(e.series,t.period,e.period)}},Jr=(t,e,r)=>{if(!t?.length)return;let o=e.start.getTime()-r.start.getTime();return t.map(s=>({...s,start:new Date(s.start.getTime()+o),actualStart:s.start}))},C=({start:t,end:e})=>e-t>Xr*yt?"day":"hour",_t=(t,e,r)=>{if(e!=="day")return new Date(t.getTime()+r*bt.hour);let o=new Date(t);return o.setDate(o.getDate()+r),o},xt=(t,e)=>{if(!t.length||!e)return t;let r=C(e),o=new Map(t.map(n=>[n.start.getTime(),n])),s=t[0].start,a=[];for(let n=0;;n--){let i=_t(s,r,n);if(i.getTime()<e.start.getTime())break;a.push(o.get(i.getTime())??gt(i))}a.reverse();for(let n=1;;n++){let i=_t(s,r,n);if(i.getTime()>=e.end.getTime())break;a.push(o.get(i.getTime())??gt(i))}return a},gt=t=>({...Ee(),start:t,costSavings:0,accruing:!1}),ke=async(t,e,r,o,s=null)=>{let a=Qr(e,o),n=a.length?await t.callWS({type:"recorder/statistics_during_period",start_time:r.start.toISOString(),end_time:r.end.toISOString(),statistic_ids:a,period:C(r),types:["change"]}):{},i=e.map(c=>to(c,n,r));return{period:r,devices:i,totals:ro(i),wholeHome:wt(o,n,r),series:eo(e,n,r,s)}},wt=(t,e,r)=>{if(!t)return;let o={};for(let[s,a]of Object.entries(O)){let n=e?.[X(t,a)];if(!Array.isArray(n))return;o[s]=kt(n,r)}return o},eo=(t,e,r,o)=>{let s=new Map;for(let n of t)for(let[i,c]of Object.entries(B)){let l=e?.[X(n,c)];for(let d of Et(l,r)){let h=s.get(d.start)??Ee();h[i]+=d.change,s.set(d.start,h)}}let a=bt[C(r)]??0;return[...s.entries()].sort(([n],[i])=>n-i).map(([n,i])=>({...i,start:new Date(n),costSavings:i.costAtGridPrice-i.actualCost,accruing:o?n+a>o.getTime():!1}))},to=(t,e,r)=>{let o=Object.fromEntries(Object.entries(B).map(([s,a])=>[s,kt(e?.[X(t,a)],r)]));return{...t,...o,...wt(t,e,r),costSavings:o.costAtGridPrice-o.actualCost}},Et=(t,{start:e,end:r})=>{if(!Array.isArray(t))return[];let o=[];for(let s of t){let a=new Date(s.start).getTime();a<e.getTime()||a>=r.getTime()||typeof s.change=="number"&&o.push({start:a,change:s.change})}return o},kt=(t,e)=>Et(t,e).reduce((r,o)=>r+o.change,0),ro=t=>({...t.reduce((r,o)=>{for(let s of Object.keys(r))r[s]+=o[s];return r},{...Ee(),costSavings:0}),...oo(t)}),oo=t=>{let e=Object.keys(O);return!t.length||!t.every(r=>e.every(o=>o in r))?{}:Object.fromEntries(e.map(r=>[r,t.reduce((o,s)=>o+s[r],0)]))};var so=`
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
`,F=class extends HTMLElement{static cardStyle="";static titleKey="";_titleKey(){return this.constructor.titleKey}get _labels(){return x(this._hass)}constructor(){super(),this.attachShadow({mode:"open"}),this._state="loading",this._request=0}setConfig(e){if(e.devices!==void 0&&!Array.isArray(e.devices))throw new Error("`devices` must be a list of device keys");this._config=e,this._render()}set hass(e){this._hass=e,this._subscription?this._subscription.retry(e):this._subscribe(),this._refetchIfDevicesChanged()}connectedCallback(){this._render(),this._hass&&!this._subscription&&this._subscribe()}disconnectedCallback(){this._subscription?.unsubscribe(),this._subscription=null,this._unfilter?.(),this._unfilter=null}_subscribe(){this._subscription=Xe(this._hass,this._config?.collection_key,e=>{this._period=e,this._scheduleFetch()}),this._unfilter=se(this._config?.collection_key,()=>this._scheduleFetch())}_scheduleFetch(){this._fetchPending||(this._fetchPending=!0,queueMicrotask(()=>{this._fetchPending=!1,this._fetch()}))}_refetchIfDevicesChanged(){let e=this._devices().map(r=>r.key).join(",");e!==this._deviceKeys&&(this._deviceKeys=e,this._period&&this._scheduleFetch())}_devices(){let e=y(this._hass),r=this._config?.devices,o=r?e.filter(a=>r.includes(a.key)):e,s=this._filter();return o.filter(a=>st(a,s))}_filter(){return Y(this._config?.collection_key)}_isFiltered(){return!!this._config?.devices||this._filter().kind!=="all"}async _fetch(){if(!this._hass||!this._period)return;let e=this._devices(),r=++this._request;if(await A(this._hass),e.length===0){this._state="empty",this._render();return}let o=this._isFiltered()?void 0:Qe(this._hass);try{let s=Je(this._hass),[a,n]=await Promise.all([ke(this._hass,e,this._period,o,s),this._period.compare?ke(this._hass,e,this._period.compare,o):void 0]);if(r!==this._request)return;this._result=vt(a,n),this._state="ready"}catch(s){if(r!==this._request)return;this._state="error",console.error(`${this.localName}: could not load statistics`,s)}this._render()}_render(){let e=ne(this._hass);this.shadowRoot.innerHTML=`
      <style>${so}${this.constructor.cardStyle}${no}</style>
      <ha-card>
        <div class="body" data-state="${this._state}">${this._content(e)}</div>
      </ha-card>
    `;let r=this._config?.title??this._labels[this._titleKey()];r&&this._writeHeader(r,e),this._afterRender()}_writeHeader(e,r){let o=this.shadowRoot.querySelector("ha-card"),s=this._headerChip(r);if(s===void 0){o.setAttribute("header",e);return}o.insertAdjacentHTML("afterbegin",`<div class="card-header" style="display: flex; justify-content: space-between;
         align-items: center; gap: var(--hea-space-s); padding-bottom: 0;">
        <span class="title">${g(e)}</span>
        <span class="chip">${g(s)}</span>
      </div>`)}_headerChip(){}_afterRender(){}_content(e){return this._state==="empty"?`<p class="message">${this._labels.no_devices}</p>`:this._state==="error"?`<p class="message">${this._labels.statistics_failed}</p>`:`${this._body(e)}${this._caption(e)}`}_caption(e){let r=this._period?.fallback?`<div class="hint">${this._labels.no_picker}</div>`:"";return`<div class="period">${this._periodLabel(e)}</div>${r}`}_periodLabel(e){let r=Z(this._period,e),o=this._period?.compare;return o?b(this._labels.compared_period,{period:r,compared:Z(o,e)}):r}},f=(t,e,{name:r,description:o})=>{customElements.get(t)||customElements.define(t,e),globalThis.customCards=globalThis.customCards??[],globalThis.customCards.some(s=>s.type===t)||globalThis.customCards.push({type:t,name:r,description:o})};var ao={title:"editor_title",collection_key:"editor_collection_key",devices:"editor_devices",sort_by:"editor_sort_by",layout:"editor_layout",metric:"editor_metric",group_by_floor:"editor_group_by_floor",group_by_area:"editor_group_by_area",range:"editor_range"},m=class extends HTMLElement{constructor(){super(),this.attachShadow({mode:"open"})}setConfig(e){this._config=e,this._render()}set hass(e){this._hass=e,this._render(),A(e).then(()=>this._render())}_extraSchema(){return[]}_render(){if(!this._config)return;let e=this.shadowRoot.querySelector("ha-form");e||(e=document.createElement("ha-form"),e.computeLabel=r=>x(this._hass)[ao[r.name]]??r.name,e.addEventListener("value-changed",r=>this._report(r.detail.value)),this.shadowRoot.append(e)),e.hass=this._hass,e.data=this._config,e.schema=this._schema()}_schema(){return[{name:"title",selector:{text:{}}},{name:"collection_key",selector:{text:{}}},{name:"devices",selector:{select:{multiple:!0,mode:"list",options:y(this._hass).map(e=>({value:e.key,label:e.name}))}}},...this._extraSchema()]}_report(e){this.dispatchEvent(new CustomEvent("config-changed",{detail:{config:io({...this._config,...e})},bubbles:!0,composed:!0}))}},io=t=>Object.fromEntries(Object.entries(t).filter(([,e])=>e!==""&&e!==void 0&&e!==null&&!(Array.isArray(e)&&e.length===0))),_=(t,e)=>{customElements.get(t)||customElements.define(t,e)};var w=class extends F{static chartTag="ha-chart-base";static bearingCard={type:"statistics-graph",entities:[]};static emptyKey="no_cost_in_period";static chartHeight="clamp(320px, 40vw, 480px)";static cardStyle=`
    ha-chart-base { display: block; --chart-max-height: none; }
  `;constructor(){super(),this._chartReady=!!customElements.get(this.constructor.chartTag)}getCardSize(){return 6}static narrowQuery="";connectedCallback(){super.connectedCallback(),this._chartReady||this._loadChartComponent(),this._watchScreen()}disconnectedCallback(){super.disconnectedCallback(),this._screen?.removeEventListener?.("change",this._onScreenChange),this._screen=null}_watchScreen(){let{narrowQuery:e}=this.constructor;!e||this._screen||(this._screen=globalThis.matchMedia?.(e),this._onScreenChange??=()=>this._render(),this._screen?.addEventListener?.("change",this._onScreenChange))}async _loadChartComponent(){let{chartTag:e,bearingCard:r}=this.constructor;customElements.whenDefined(e).then(()=>{this._chartReady=!0,this._render()});try{await(await globalThis.loadCardHelpers?.())?.createCardElement(r)}catch(o){console.warn(`${e}: could not be loaded`,o)}}_isEmpty(){return(this._result?.series??[]).length===0}_body(){return this._chartReady?this._isEmpty()?`<p class="message">${this._labels[this._emptyKey()]}</p>`:this._chartMarkup():`<p class="message">${this._labels.chart_not_loaded}</p>`}_emptyKey(){return this.constructor.emptyKey}_chartMarkup(){return'<ha-chart-base chart-type="bar"></ha-chart-base>'}_afterRender(){let e=this.shadowRoot.querySelector(this.constructor.chartTag);e&&(e.hass=this._hass,this._draw(e))}_chartHeight(){return this.constructor.chartHeight}_draw(e){e.height=this._chartHeight(),e.data=this._series(),e.options=this._options(this._chartLocale())}_chartLocale(){return ne(this._hass)}_colour({variable:e,fallback:r}){return getComputedStyle(this).getPropertyValue(e).trim()||r}};var co=/^#([\da-f]{3}|[\da-f]{6})$/i,lo=/^rgba?\(([^)]+)\)$/i,Se=t=>{let e=co.exec(String(t).trim());if(e){let s=e[1];return(s.length===3?[...s].map(n=>n+n):[0,2,4].map(n=>s.slice(n,n+2))).map(n=>Number.parseInt(n,16))}let r=lo.exec(String(t).trim());if(!r)return;let o=r[1].split(/[\s,/]+/).filter(Boolean).slice(0,3).map(Number);return o.length===3&&o.every(Number.isFinite)?o:void 0},S=(t,e)=>{let r=Se(String(t).trim());return r?`rgba(${r.join(", ")}, ${e})`:t},uo=([t,e,r])=>(.2126*t+.7152*e+.0722*r)/255,ae=t=>{let e=Se(ho(t));return e?uo(e)>.5:!1},ho=t=>{let e=[t,t?.ownerDocument?.documentElement].filter(Boolean);for(let r of e){let o=getComputedStyle(r),s=o.getPropertyValue("--primary-text-color").trim()||o.color;if(Se(s))return s}return""};var St=Object.freeze({variable:"--primary-color",fallback:"#03a9f4"}),Tt=Object.freeze({variable:"--success-color",fallback:"#4caf50"}),mo=Object.freeze({paid:"paid",would_have_paid:"would-have-paid",saved:"saved"}),ie=`
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
`,ce=t=>{let e=typeof t=="string"?mo[t]:void 0;return e?`<span class="swatch ${e}" aria-hidden="true"></span>`:""};var $=(t,e,r,{bold:o=!1}={})=>{let s=document.createElement("div");s.style.display="flex",s.style.justifyContent="space-between",s.style.gap="16px",o&&(s.style.fontWeight="bold");let a=document.createElement("span");a.textContent=t;let n=document.createElement("span");return n.textContent=e,n.style.fontVariantNumeric="tabular-nums",r&&(n.style.color=r),s.append(a,n),s},po=t=>{let e=document.createElement("span");return e.style.display="inline-block",e.style.width="10px",e.style.height="10px",e.style.borderRadius="10px",e.style.marginInlineEnd="4px",e.style.verticalAlign="middle",e.style.backgroundColor=t,e},At=(t,e,r,o)=>{let s=$(e,r,o);return s.firstChild.prepend(po(t)),s},le=t=>{let e=document.createElement("div");return e.textContent=t,e.style.fontWeight="bold",e.style.textAlign="center",e.style.marginBottom="4px",e},Ot=t=>{let e=document.createElement("div");return e.textContent=t,e.style.marginTop="4px",e.style.maxWidth="260px",e.style.whiteSpace="normal",e.style.opacity="0.7",e};var Rt="hea-cost-over-time-card",It=`${Rt}-editor`,fo={hour:3600*1e3,day:1440*60*1e3},_o=50,go=.5,yo=(t,e)=>{if(!t.length||!e)return 0;let r=fo[C(e)]??0,o=t.length>=2?t[1].start.getTime()-t[0].start.getTime():void 0;return(o?Math.min(o,r):r)/2},R={paid:{id:"paid",name:"paid",...St},saved:{id:"saved",name:"saved",...Tt}},Nt={variable:"--error-color",fallback:"#db4437"},bo={gain:{variable:"--success-color",fallback:"#4caf50"},loss:Nt},Te=t=>t.value?.[1]??0,vo=t=>t.value?.[2],xo=.45,de={id:"before",name:"compared_series",variable:"--secondary-text-color",fallback:"#727272"},Ae=class extends w{static titleKey="title_cost_over_time";static getConfigElement(){return document.createElement(It)}_series(){let e=xt(this._result?.series??[],this._result?.period),r=this._colour(Nt),o=this._labels,s=this._result?.seriesBefore,a=yo(e,this._result?.period);return[...te([{...$t(R.paid,this._colour(R.paid),o),data:e.map(n=>Ct(n,Ft(n,n.actualCost,a)))},{...$t(R.saved,this._colour(R.saved),o),data:e.map(n=>{let i=Ft(n,n.costSavings,a),c=n.costSavings<0?Dt(r):void 0;return Ct(n,i,c)})}]),...s?.length?[{id:de.id,name:o[de.name],type:"line",symbol:"none",lineStyle:{type:"dashed",width:2},itemStyle:{color:this._colour(de)},data:s.map(n=>[n.start.getTime()+a,n.costAtGridPrice])}]:[]]}_caption(e){return`${super._caption(e)}${this._stillAccruingNote()}`+this._accrualNote()}_stillAccruingNote(){return(this._result?.series??[]).some(e=>e.accruing)?`<div class="hint">${this._labels.still_accruing}</div>`:""}_accrualNote(){return this._devices().length!==1||!this._period||C(this._period)!=="hour"?"":`<div class="hint">${this._labels.hourly_shape_estimate}</div>`}_tooltipFor(e,r){let o=(Array.isArray(e)?e:[e]).filter(c=>c.componentSubType==="bar"),s=o.filter(c=>Te(c)!==0);if(!s.length)return;let a=this._bucketAt(o.map(vo).find(c=>c!==void 0)),n=document.createElement("div");n.append(le(this._spanOf(a,r)));for(let c of s)n.append(this._tooltipRowFor(c,r));let i=o.reduce((c,l)=>c+Te(l),0);return s.length>1&&n.append($(this._labels.would_have_paid,u(i,r),void 0,{bold:!0})),a?.accruing&&n.append(Ot(this._labels.still_accruing)),n}_tooltipRowFor(e,r){let o=Te(e),a=e.seriesId===R.saved.id&&o<0?this._labels.lost:e.seriesName,n=e.seriesId===R.saved.id?T(o):"";return At(e.color,a,u(o,r),n?this._colour(bo[n]):void 0)}_bucketAt(e){if(e!==void 0)return(this._result?.series??[]).find(r=>r.start.getTime()===e)}_spanOf(e,r){return!e||!this._period?"":at(e.start,C(this._period),r)}_headerChip(e){let r=this._result?.totals?.actualCost;return Number.isFinite(r)&&!this._isEmpty()?u(r,e):""}_axisBounds(){if(!this._period)return{};let{start:e,end:r}=this._period,o=new Date(r.getTime()-1);return C(this._period)==="hour"?o.setMinutes(30,0,0):(o.getHours()===0&&o.setHours(o.getHours()-1),o.setHours(0,0,0,0)),{min:e.getTime(),max:o.getTime()}}_options(e){let r=this._labels;return{xAxis:{type:"time",...this._axisBounds()},grid:{top:15,bottom:0,left:1,right:1,containLabel:!0},yAxis:{type:"value",name:q(e),nameGap:2,nameTextStyle:{align:"left"},boundaryGap:[0,0],splitNumber:5,splitLine:{show:!0},axisLabel:{formatter:o=>V(o,e),hideOverlap:!0}},tooltip:{trigger:"axis",axisPointer:{type:"shadow"},formatter:o=>this._tooltipFor(o,e)},legend:{show:!0,type:"custom",data:[R.paid,R.saved,...this._result?.seriesBefore?.length?[de]:[]].map(o=>({id:o.id,name:r[o.name],itemStyle:{color:this._colour(o)}}))}}}},Ct=(t,e,r=void 0)=>t.accruing?{value:e,itemStyle:{...r,opacity:xo}}:r?{value:e,itemStyle:r}:e,Ft=(t,e,r)=>[t.start.getTime()+r,e,t.start.getTime()],$t=({id:t,name:e},r,o)=>({id:t,name:o[e],type:"bar",stack:"cost",barMaxWidth:_o,itemStyle:Dt(r)}),Dt=t=>({color:S(t,go),borderColor:t,borderWidth:1}),Oe=class extends m{},wo=()=>{_(It,Oe),f(Rt,Ae,{name:"Home Energy Advisor: Cost over time",description:"What the period cost, stacked against what it would have cost at grid price."})};wo();var $e="hea",Ht="Home Energy Advisor",Eo="mdi:home-lightning-bolt",Mt=`ll-strategy-dashboard-${$e}`,Lt=`ll-strategy-view-${$e}`,ko=[{type:"custom:hea-totals-card"},{type:"custom:hea-devices-card",sort_by:"actual_cost"},{type:"custom:hea-cost-over-time-card"},{type:"custom:hea-sources-card",sort_by:"energy_used"}],So=[{type:"custom:hea-device-costs-card"},{type:"custom:hea-distribution-card"},{type:"custom:hea-self-sufficiency-card"}],To=t=>({...t,grid_options:{columns:"full",rows:"auto"}}),Gt=t=>({type:"grid",column_span:2,cards:t.map(To)}),Ao=()=>({card:{type:"horizontal-stack",cards:[{type:"energy-date-selection",vertical_opening_direction:"up"},{type:"custom:hea-filter-card"}]},max_width:1600}),Oo=t=>({type:"sections",max_columns:4,sections:[{type:"grid",cards:[{type:"markdown",content:x(t).no_devices}]}]}),Co=t=>y(t).length===0?Oo(t):{type:"sections",max_columns:4,sections:[Gt(ko),Gt(So)],footer:Ao()},Pt=async t=>(await A(t),Co(t)),Ce=class extends HTMLElement{static async generate(e,r){return{views:[await Pt(r)]}}static noEditor=!0;static getCreateSuggestions(){return{title:Ht,icon:Eo}}},Fe=class extends HTMLElement{static async generate(e,r){return Pt(r)}},Fo=t=>{globalThis.customStrategies=globalThis.customStrategies??[],globalThis.customStrategies.some(e=>e.type===t.type)||globalThis.customStrategies.push(t)},$o=()=>{customElements.get(Mt)||customElements.define(Mt,Ce),customElements.get(Lt)||customElements.define(Lt,Fe),Fo({type:$e,strategyType:"dashboard",name:Ht,description:"What each device cost to run, and what solar and the battery saved."})};$o();var jt=Object.keys(B),Ro=Object.keys(O),Ut=t=>{let e=new Map;for(let r of t){if(!r.upstream)continue;let o=e.get(r.upstream);o?o.push(r):e.set(r.upstream,[r])}return e},ue=(t,e)=>({...t,key:`${t.key}${Io}`,name:`${t.name} ${e.device_untracked}`,upstream:t.key,untracked:!1,residualOf:t.key}),Io="__untracked",No=t=>{let e=Object.fromEntries(jt.map(r=>[r,0]));for(let r of t)for(let o of jt)e[o]+=r[o]??0;for(let r of Ro)e[r]=t.every(o=>typeof o[r]=="number")?t.reduce((o,s)=>o+s[r],0):void 0;return e.costSavings=e.costAtGridPrice-e.actualCost,e},he=(t,e)=>{let r=Ut(t);return r.size===0?t:t.flatMap(o=>r.has(o.key)?[ue(o,e)]:[o])},Bt=(t,e,r=o=>o)=>{let o=Ut(t);if(o.size===0)return r(t).map(a=>({device:a,depth:0}));let s=(a,n)=>{if(!o.has(a.key))return[{device:a,depth:n}];let c=r([...o.get(a.key),ue(a,e)]).flatMap(d=>s(d,n+1)),l=c.filter(d=>!d.device.subtotal).map(d=>d.device);return[{device:{...a,...No(l),subtotal:!0},depth:n},...c]};return r(t.filter(a=>!a.upstream)).flatMap(a=>s(a,0))};var E=Object.freeze(["#0072b2","#e69f00","#009e73","#cc79a7","#56b4e9","#d55e00","#8c6bb1","#3d9970"]),Do=Object.freeze(["#4b46b3","#8d9b1f","#00a2ab","#b07ad2","#7fa0ee","#a8761b","#b26596","#5b8f3f"]),Re=Object.freeze([E,Do]),Tn=E.length*Re.length,z=Object.freeze({variable:"--secondary-text-color",fallback:"#8a8a8a"}),W=t=>{let e=(t??[]).filter(r=>!r.untracked).map(r=>r.key).sort(Mo);return new Map(e.map((r,o)=>{let s=Math.floor(o/E.length)%Re.length;return[r,Re[s][o%E.length]]}))},Mo=(t,e)=>t===e?0:t<e?-1:1;var me=(t,e,r)=>{let o=t<0?e.lost_share:e.saved_share;return b(o,{percent:U(Math.abs(t),r)})},Lo=({costSavings:t,costAtGridPrice:e})=>{if(!(!Number.isFinite(t)||!Number.isFinite(e))&&!(e<=0))return t/e},Q=[{at:0,hue:3,light:48,dark:62},{at:.5,hue:35,light:46,dark:68},{at:1,hue:142,light:31,dark:76}],zt={light:85,dark:70},Go=.7,Wt=(t,e,r)=>t+(e-t)*r,Ho=.6,Po=(t,e)=>{let r=Q.findIndex(i=>t<=i.at);if(r<=0)return{hue:Q[0].hue,lightness:Q[0][e]};let o=Q[r-1],s=Q[r],a=(t-o.at)/(s.at-o.at),n=r===1?a:a**Ho;return{hue:Wt(o.hue,s.hue,n),lightness:Wt(o[e],s[e],a)}},Kt=.05,D=t=>Math.round(t*10)/10,pe=(t,{dark:e=!1}={})=>{let r=e?"dark":"light",o=a=>Math.max(0,a?.costAtGridPrice??0),s=Math.max(0,...(t??[]).map(o));return a=>{let n=Lo(a??{});if(n===void 0||s<=0)return;let i=Math.min(1,o(a)/s),c=i*(1+Kt)/(i+Kt),l=Math.min(1,Math.max(0,n)),{hue:d,lightness:h}=Po(l,r),v=zt[r]*c**Go;return{rate:n,text:`hsl(${D(d)}, ${D(v)}%, ${D(h)}%)`,edge:`hsla(${D(d)}, ${D(zt[r])}%, ${D(h)}%, ${D(c)})`}}};var er="hea-device-costs-card",tr=`${er}-editor`,Yt={variable:"--error-color",fallback:"#db4437"},jo={variable:"--secondary-text-color",fallback:"#727272"},Uo="earlier-period",Bo=["auto","vertical","horizontal"],Vt="(max-width: 767px)",zo="paid",Wo="saved",qt="before",Ko=30,Yo=46,Vo=64,qo=240,Zo=24,Xo=12,Qo=2,Jo=10,es=300,ts=120,rs="40vw",os={left:8,right:16,top:8,bottom:28,containLabel:!0},Zt=1.5,Xt=.8,Qt=.45,Jt=.22,ss=/:(?:paid|saved|before)$/,ns={gain:{variable:"--success-color",fallback:"#4caf50"},loss:{variable:"--error-color",fallback:"#db4437"}},as=(t,e,r,o,s,a)=>{let n=T(t.costSavings),i=document.createElement("div");i.append(le(e),$(o.paid,u(t.actualCost,r)),$(t.costSavings<0?o.lost:o.saved,u(t.costSavings,r),n?s(n):void 0),$(o.would_have_paid,u(t.costAtGridPrice,r)));let c=is(a,r,o);c&&i.append(c);let l=cs(t,r,o,s);l&&i.append(l);let d=ls(t,r,o);return d&&i.append(d),i},is=(t,e,r)=>{if(!t)return;let o=document.createElement("div");return o.style.marginTop="4px",o.style.color=t.text,o.textContent=me(t.rate,r,e),o},cs=(t,e,r,o)=>{let s=t.before?.actualCost;if(!Number.isFinite(s)||!Number.isFinite(t.actualCost))return;let a=t.actualCost-s,n=j("actualCost",a);return $(r.change,b(r.compared,{change:P(a,e),before:u(s,e)}),n?o(n):void 0)},ls=({costFloor:t,costCeiling:e},r,o)=>{if(![t,e].every(a=>Number.isFinite(a)))return;let s=document.createElement("div");return s.style.marginTop="4px",s.style.opacity="0.75",s.textContent=b(o.range_device,{range:N([t,e],r)}),s},Ie=class extends w{static titleKey="title_device_costs";static narrowQuery=Vt;static getConfigElement(){return document.createElement(tr)}_isEmpty(){return this._ranked().every(e=>!e.costAtGridPrice&&!e.actualCost)}_ranked(){return he(this._result?.devices??[],this._labels).sort((e,r)=>r.actualCost-e.actualCost||e.name.localeCompare(r.name))}_colourFor(e){if(e.untracked)return this._colour(z);let r=e.residualOf??e.key;return this._colours().get(r)??E[0]}_colours(){return W(y(this._hass))}_verdicts(){return pe(this._ranked(),{dark:ae(this)})}_sideways(){let e=this._config?.layout;return e==="horizontal"?!0:e==="vertical"?!1:!!globalThis.matchMedia?.(Vt)?.matches}_comparing(){return this._ranked().some(e=>e.before)}_series(){return te(this._sideways()?this._sidewaysSeries():this._standingSeries())}_sidewaysSeries(){let e=this._ranked(),r=this._colour(Yt),o=this._labels,s=a=>this._colourFor(a);return[{id:zo,name:o.paid,type:"bar",stack:"cost",data:e.map(a=>({value:a.actualCost,itemStyle:{color:S(s(a),Xt)}}))},{id:Wo,name:o.saved,type:"bar",stack:"cost",data:e.map(a=>{let n=a.costSavings<0?r:s(a);return{value:a.costSavings,itemStyle:{color:S(n,Jt),borderColor:n,borderWidth:Zt}}})},...this._comparing()?[{id:qt,name:o.compared_series,type:"bar",stack:"earlier",data:e.map(a=>({value:a.before?a.before.actualCost:null,itemStyle:{color:S(s(a),Qt)}}))}]:[]]}_standingSeries(){let e=this._colour(Yt);return this._ranked().flatMap(r=>{let o=this._colourFor(r),s=r.costSavings<0?e:o,a=r.name;return[{id:`${r.key}:paid`,name:a,type:"bar",stack:r.key,itemStyle:{color:S(o,Xt)},data:[r.actualCost]},{id:`${r.key}:saved`,name:a,type:"bar",stack:r.key,itemStyle:{color:S(s,Jt),borderColor:s,borderWidth:Zt},data:[r.costSavings]},...r.before?[{id:`${r.key}:before`,name:a,type:"bar",stack:`${r.key}:before`,itemStyle:{color:S(o,Qt)},data:[r.before.actualCost]}]:[]]})}_tooltipFor({seriesId:e,dataIndex:r},o){let s=this._ranked(),a=this._sideways()?s[r]:s.find(n=>n.key===String(e??"").replace(ss,""));return a?as(a,a.name,o,this._labels,n=>this._colour(ns[n]),this._verdicts()(a)):void 0}_earlierKey(){if(!this._comparing())return[];let e=this._labels.compared_series,r={color:this._colour(jo)};return this._sideways()?[{id:qt,name:e,itemStyle:r}]:[{id:Uo,secondaryIds:this._ranked().filter(o=>o.before).map(o=>`${o.key}:before`),name:e,itemStyle:r}]}_chartHeight(){if(this._sideways()){let r=this._ranked().length,o=this._comparing()?Yo:Ko;return`${Math.max(qo,Vo+r*o)}px`}let e=es+this._legendHeight();return`clamp(${e}px, ${rs}, ${e+ts}px)`}_legendHeight(){let e=Math.min(this._ranked().length,Jo)+this._earlierKey().length;return Math.ceil(e/Qo)*Zo+Xo}_options(e){return this._sideways()?this._sidewaysOptions(e):this._standingOptions(e)}_sidewaysOptions(e){let r=this._earlierKey();return{xAxis:{type:"value",name:q(e),axisLabel:{formatter:o=>V(o,e),hideOverlap:!0}},yAxis:{type:"category",data:this._ranked().map(o=>o.name),inverse:!0},grid:os,tooltip:{trigger:"item",formatter:o=>this._tooltipFor(o,e)},...r.length?{legend:{show:!0,type:"custom",data:r}}:{}}}_standingOptions(e){return{xAxis:{type:"category",data:[Z(this._period,e)]},yAxis:{type:"value",name:q(e),nameGap:2,nameTextStyle:{align:"left"},axisLabel:{formatter:r=>V(r,e),hideOverlap:!0}},tooltip:{trigger:"item",formatter:r=>this._tooltipFor(r,e)},legend:{show:!0,type:"custom",data:[...this._ranked().map(r=>({id:`${r.key}:paid`,secondaryIds:[`${r.key}:saved`,...r.before?[`${r.key}:before`]:[]],name:r.name,itemStyle:{color:this._colourFor(r)}})),...this._earlierKey()]}}}},Ne=class extends m{_extraSchema(){return[{name:"layout",selector:{select:{mode:"dropdown",options:Bo}}}]}},ds=()=>{_(tr,Ne),f(er,Ie,{name:"Home Energy Advisor: Device costs (chart)",description:"What each device cost over the selected period, dearest first."})};ds();var us=`${ie}
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
`,rr=(t,e,r)=>{let o=t==="costSavings"?T(r):j(e,r);return o?` class="${o}"`:""},or=t=>t?` style="box-shadow: inset ${hs} 0 0 ${t.edge}"`:"",hs="4px",M=class extends F{static columns=[];static sorts={};static defaultSort="";static cardStyle=us;setConfig(e){let{sorts:r}=this.constructor;if(e.sort_by!==void 0&&!(e.sort_by in r))throw new Error(`\`sort_by\` must be one of: ${Object.keys(r).join(", ")}`);super.setConfig(e)}getCardSize(){return 3+Math.ceil((this._result?.devices.length??3)/2)}_columns(){return this.constructor.columns}_body(e){let r=this._columns(),o=this._verdictScale();return`
      <div class="scroll">
        <table>
          <thead><tr>${r.map(s=>this._heading(s,e)).join("")}</tr></thead>
          <tbody>${this._ranked().map(({device:s,depth:a})=>this._row(s,e,o,a)).join("")}</tbody>
          <tfoot>${this._total(e,o)}</tfoot>
        </table>
      </div>`}_verdictScale(){if(this._columns().some(e=>e.carriesVerdict))return pe(this._result?.devices??[],{dark:ae(this)})}_heading({label:e},r){let o=this._labels;if(typeof e!="function")return`<th>${ce(e)}${o[e]}</th>`;let{text:s,unit:a}=e(r,o);return`<th>${s} <span class="unit">${g(a)}</span></th>`}_rank(e){let{sorts:r,defaultSort:o}=this.constructor,{field:s}=r[this._config?.sort_by??o];return[...e].sort((a,n)=>n[s]-a[s]||a.name.localeCompare(n.name))}_ranked(){return Bt(this._result?.devices??[],this._labels,e=>this._rank(e))}_row(e,r,o,s){return`<tr${e.subtotal?' class="subtotal"':""}>${this._columns().map(n=>this._cell(n,e,r,o?.(e),s)).join("")}</tr>`}_cell({field:e,derive:r,format:o,tone:s,carriesVerdict:a,reveal:n},i,c,l,d){if(!o)return`<th scope="row"${d?` class="inside" style="--depth: ${d}"`:""}${or(l)}>${g(i.name)}</th>`;let h=r?r(i):i[e],v=a?this._verdictOn(l,c):"",I=this._revealed(o(h,c),n?.(i,c,this._labels));return`<td${rr(e,s,h)}${v}>${I}</td>`}_revealed(e,r){return r?`<span class="reveal" tabindex="0" aria-label="${g(r.label)}">${e}<span class="revealed" aria-hidden="true">${g(r.text)}</span></span>`:e}_total(e,r){let o=this._sumOfShown(),s=r?.(o);return`<tr>${this._columns().map(({field:n,derive:i,format:c,tone:l,carriesVerdict:d})=>{if(!c)return`<th scope="row"${or(s)}>${this._labels.total}</th>`;let h=i?i(o):o[n],v=d?this._verdictOn(s,e):"";return`<td${rr(n,l,h)}${v}>${c(h,e)}</td>`}).join("")}</tr>`}_verdictOn(e,r){if(!e)return"";let o=me(e.rate,this._labels,r);return` style="color: ${e.text}" title="${g(o)}"`}_sumOfShown(){let e=[...new Set(this._columns().flatMap(({field:n,fields:i,derive:c,format:l})=>l?c?i??[]:n?[n]:[]:[]))],r=he(this._result?.devices??[],this._labels),o=Object.fromEntries(this._columns().flatMap(({fields:n,field:i,readField:c})=>c?(n??[i]).map(l=>[l,c]):[])),s=n=>r.reduce((i,c)=>{for(let l of e){let d=n(c);i[l]+=o[l]?o[l](d,l):d[l]}return i},Object.fromEntries(e.map(i=>[i,0]))),a=s(n=>n);return r.length>0&&r.every(n=>n.before)&&(a.before=s(n=>n.before)),a}},fe=(t,e)=>[{name:"sort_by",selector:{select:{mode:"dropdown",options:Object.entries(t).map(([r,{label:o}])=>({value:r,label:e[o]}))}}}];var nr="hea-devices-card",ar=`${nr}-editor`,ms=({actualCost:t,energyUsed:e})=>e>0?t/e:void 0,Le=t=>Object.values(O).every(e=>e in(t.statistics??{})),L={fields:["costFloor","costCeiling"],derive:({costFloor:t,costCeiling:e})=>[t,e],label:"range_column",format:N,readField:(t,e)=>Number.isFinite(t[e])?t[e]:t.actualCost},ir={fields:["actualCost"],derive:({actualCost:t,before:e})=>e&&Number.isFinite(t)&&Number.isFinite(e.actualCost)?t-e.actualCost:void 0,label:"change",format:P,tone:"actualCost"},_e={field:"actualCost",label:"paid",format:u,reveal:(t,e)=>{if(!Le(t)||!L.fields.every(o=>Number.isFinite(t[o])))return null;let r=N(L.derive(t),e);return{text:r,label:`${u(t.actualCost,e)} (${r})`}}},ps={fields:["actualCost","forgoneExport"],derive:t=>t.actualCost+(t.forgoneExport??0),label:"paid_with_forgone",format:u,reveal:(t,e,r)=>{let o=t.forgoneExport??0;if(!Number.isFinite(o)||o<=0)return _e.reveal(t,e);let s={paid:u(t.actualCost,e),forgone:u(o,e)},n=Le(t)&&L.fields.every(c=>Number.isFinite(t[c]))?b(r.paid_breakdown,{...s,range:N(L.derive(t),e)}):b(r.paid_breakdown_unranged,s),i=u(t.actualCost+o,e);return{text:n,label:`${r.paid_with_forgone} ${i}: ${n}`}}},cr={field:"forgoneExport",label:"forgone_column",format:u},sr=[{field:"name",label:"device"},{field:"energyUsed",label:"energy",format:k},_e,ir,L,cr,{field:"costAtGridPrice",label:"would_have_paid",format:u,carriesVerdict:!0},{field:"costSavings",label:"saved",format:u},{derive:ms,label:(t,e)=>({text:e.rate,unit:lt(t)}),format:dt}],lr={actual_cost:{field:"actualCost",label:"paid"},cost_at_grid_price:{field:"costAtGridPrice",label:"would_have_paid"},cost_savings:{field:"costSavings",label:"saved"},energy_used:{field:"energyUsed",label:"energy_used"}},De=class extends M{static titleKey="title_devices";static columns=sr;static sorts=lr;static defaultSort="actual_cost";static cardStyle=`${M.cardStyle}
    .disclosure {
      margin-top: var(--hea-space-m);
      color: var(--secondary-text-color);
      font-size: 0.8em;
    }
  `;static getConfigElement(){return document.createElement(ar)}_columns(){let e=this._rangeAsColumn(),r=this._withForgone(),o=r?ps:_e,s=new Set;return e||s.add(L),e&&r||s.add(cr),this._hasComparison()||s.add(ir),sr.filter(a=>!s.has(a)).map(a=>a!==_e?a:e?{...o,reveal:void 0}:o)}_rangeAsColumn(){return this._config?.range==="column"&&this._hasEveryBound()}_withForgone(){return this._config?.forgone!=="exclude"&&this._hasForgone()}_hasComparison(){return(this._result?.devices??[]).some(e=>e.before)}_hasForgone(){return(this._result?.devices??[]).some(e=>(e.forgoneExport??0)>0)}_hasEveryBound(){let e=(this._result?.devices??[]).filter(Le);return e.length>0&&e.every(r=>L.fields.every(o=>Number.isFinite(r[o])))}_body(e){return`${super._body(e)}${this._disclosure(e)}`}_disclosure(e){let r=this._labels;if(this._hasEveryBound())return`<div class="disclosure">${this._rangeNote()}</div>`;let o=this._result?.wholeHome;if(!o)return"";let s=N([o.costFloor,o.costCeiling],e);return`<div class="disclosure">
      ${b(r.range_whole_home,{range:s})}
    </div>`}_rangeNote(){let e=this._labels;return this._rangeAsColumn()?this._withForgone()?`${e.range_note} ${e.range_note_not_cost_of_use}`:e.range_note:this._withForgone()?e.range_note_cost_of_use:e.range_note_rollover}},Me=class extends m{_extraSchema(){let e=x(this._hass);return[...fe(lr,e),{name:"forgone",selector:{select:{mode:"dropdown",options:[{value:"include",label:e.editor_forgone_include},{value:"exclude",label:e.editor_forgone_exclude}]}}},{name:"range",selector:{select:{mode:"dropdown",options:[{value:"rollover",label:e.editor_range_rollover},{value:"column",label:e.editor_range_column}]}}}]}},fs=()=>{_(ar,Me),f(nr,De,{name:"Home Energy Advisor: Devices",description:"Every tracked device over the selected period, ordered by what it cost."})};fs();var J="household",K=Object.freeze({source:0,household:1,floor:2,area:3,device:4}),dr=Object.freeze({cost:{field:"actualCost",sources:null},energy:{field:"energyUsed",sources:[{id:"grid",field:"energyFromGrid",variable:"--energy-grid-consumption-color",fallback:"#488fc2"},{id:"generation",field:"energyFromGeneration",variable:"--energy-solar-color",fallback:"#ff9800"},{id:"battery",field:"energyFromBattery",variable:"--energy-battery-out-color",fallback:"#4db6ac"}]}}),_s=t=>{let e=W(t);return r=>r.untracked?z.fallback:e.get(r.key)??E[0]},gs=({fallback:t})=>t,pr=(t,e,{metric:r="cost",colour:o=gs,deviceColour:s=_s(t),groupByFloor:a=!0,groupByArea:n=!0}={})=>{let{field:i,sources:c}=dr[r]??dr.cost,l=ys(t,i).filter(p=>p.value>0);if(l.length===0)return{nodes:[],links:[]};let d=l.reduce((p,Cr)=>p+Cr.value,0),h=vs(l,{groupByFloor:a,groupByArea:n}),v=xs(l,e,s),I=ws(c,t.filter(p=>p[i]>0),e,o);return{nodes:[...I,{id:J,label:e.household,value:d,index:K.household},...h.nodes,...v.nodes],links:[...I.map(p=>({source:p.id,target:J,value:p.value})),...h.links,...v.links]}},ys=(t,e)=>{let r=new Map(t.map(n=>[n.key,n])),o=new Map,s=[];for(let n of t){let i=bs(n,r);i?o.has(i.key)?o.get(i.key).push(n):o.set(i.key,[n]):s.push(n)}let a=n=>{let i=Math.max(n[e]??0,0),c=(o.get(n.key)??[]).map(a).filter(l=>l.value>0);return{device:n,own:i,inside:c,value:c.reduce((l,d)=>l+d.value,i)}};return s.map(a)},bs=(t,e)=>{let r=e.get(t.upstream);if(!r)return null;let o=new Set;for(let s=r;s;s=e.get(s.upstream)){if(s.key===t.key)return null;if(o.has(s.key))break;o.add(s.key)}return r},vs=(t,{groupByFloor:e,groupByArea:r})=>{let o=new Map,s=new Map,a=[];return t.forEach(({device:n,value:i})=>{let c=e&&n.floorId?ur(o,n.floorId,n.floorName):null,l=r&&n.areaId?ur(s,n.areaId,n.areaName):null;c&&(c.value+=i),l&&(l.value+=i,l.floorId??=c?.id??null),a.push({source:Es(l,c),target:G(n),value:i})}),{nodes:[...mr(o,"floor_",K.floor),...mr(s,"area_",K.area)],links:[...ks(o,s),...a]}},xs=(t,e,r)=>{let o=K.device+fr(t),s=[],a=[],n=(i,c)=>{let{device:l,own:d,inside:h,value:v}=i,I=h.length>0;if(s.push({id:G(l),label:l.name,value:v,index:I?K.device+c:o,color:r(l),...hr(l)}),!!I&&(h.forEach(p=>{a.push({source:G(l),target:G(p.device),value:p.value}),n(p,c+1)}),d>0)){let p=ue(l,e);s.push({id:G(p),label:p.name,value:d,index:o,color:r(l),...hr(l)}),a.push({source:G(l),target:G(p),value:d})}};return t.forEach(i=>n(i,0)),{nodes:s,links:a}},fr=t=>t.reduce((e,r)=>r.inside.length>0?Math.max(e,1+fr(r.inside)):e,0),G=t=>`device_${t.key}`,ws=(t,e,r,o)=>(t??[]).map(s=>({id:`source_${s.id}`,label:r[s.id],value:e.reduce((a,n)=>a+(n[s.field]??0),0),index:K.source,color:o(s)})).filter(s=>s.value>0),ur=(t,e,r)=>(t.has(e)||t.set(e,{id:e,name:r||e,value:0}),t.get(e)),Es=(t,e)=>t?`area_${t.id}`:e?`floor_${e.id}`:J,hr=t=>{let e=t.statistics?.actual_cost;return e?{entityId:e}:{}},mr=(t,e,r)=>[...t.values()].map(o=>({id:`${e}${o.id}`,label:o.name,value:o.value,index:r})),ks=(t,e)=>[...[...t.values()].map(r=>({source:J,target:`floor_${r.id}`,value:r.value})),...[...e.values()].map(r=>({source:r.floorId?`floor_${r.floorId}`:J,target:`area_${r.id}`,value:r.value}))];var gr="hea-distribution-card",yr=`${gr}-editor`,ee={cost:{titleKey:"title_distribution",emptyKey:"no_cost_in_period",format:u},energy:{titleKey:"title_distribution_energy",emptyKey:"no_energy_in_period",format:k}},_r="(max-width: 767px)",Ss="400px",Ts=88,As=240,Os=["auto","horizontal","vertical"],Ge=Object.freeze({group_by_floor:!0,group_by_area:!0}),He=class extends w{static titleKey="title_distribution";static chartTag="ha-sankey-chart";static bearingCard={type:"energy-sankey"};static narrowQuery=_r;static cardStyle=`
    ha-sankey-chart { display: block; min-height: 240px; }
  `;static getConfigElement(){return document.createElement(yr)}_isEmpty(){return this._layout().nodes.length===0}_verticalHeight({nodes:e}){let r=new Set(e.map(o=>o.index)).size;return`${Math.max(As,r*Ts)}px`}_metric(){return ee[this._config?.metric]?this._config.metric:"cost"}_titleKey(){return ee[this._metric()].titleKey}_emptyKey(){return ee[this._metric()].emptyKey}_layout(){let e=W(y(this._hass));return pr(this._result?.devices??[],this._labels,{metric:this._metric(),groupByFloor:this._config?.group_by_floor??Ge.group_by_floor,groupByArea:this._config?.group_by_area??Ge.group_by_area,colour:r=>this._colour(r),deviceColour:r=>r.untracked?this._colour(z):e.get(r.key)??E[0]})}_chartMarkup(){return"<ha-sankey-chart></ha-sankey-chart>"}_draw(e){e.data=this._layout(),e.vertical=this._isVertical(),e.style.height=this._isVertical()?this._verticalHeight(e.data):Ss;let r=this._chartLocale(),{format:o}=ee[this._metric()];e.valueFormatter=s=>o(s,r),this.toggleAttribute("data-vertical",e.vertical)}_isVertical(){let e=this._config?.layout;return e==="vertical"?!0:e==="horizontal"?!1:!!globalThis.matchMedia?.(_r)?.matches}},Pe=class extends m{_extraSchema(){return[{name:"metric",selector:{select:{mode:"dropdown",options:Object.keys(ee)}}},{name:"layout",selector:{select:{mode:"dropdown",options:Os}}},{name:"group_by_floor",selector:{boolean:{}}},{name:"group_by_area",selector:{boolean:{}}}]}setConfig(e){super.setConfig({...Ge,...e})}},Cs=()=>{_(yr,Pe),f(gr,He,{name:"Home Energy Advisor: Cost distribution",description:"Where the period's cost went, by floor, room, circuit and device."})};Cs();var br="hea-filter-card",vr=`${br}-editor`,Fs=[{kind:"area",label:"filter_rooms",id:"areaId",name:"areaName"},{kind:"floor",label:"filter_floors",id:"floorId",name:"floorName"}],H=({kind:t,id:e})=>`${t}:${e??""}`,$s=t=>{let[e,r]=[t.slice(0,t.indexOf(":")),t.slice(t.indexOf(":")+1)];return{kind:e,id:r===""?null:r}},je=class extends HTMLElement{constructor(){super(),this.attachShadow({mode:"open"})}setConfig(e){this._config=e,this._render()}set hass(e){this._hass=e,A(e).then(()=>this._renderIfChanged()),this._renderIfChanged()}getCardSize(){return 1}static getConfigElement(){return document.createElement(vr)}connectedCallback(){this._render(),this._unfilter??=se(this._config?.collection_key,()=>this._renderIfChanged())}_signature(){return JSON.stringify([this._allDevices().map(e=>[e.key,e.name,e.areaId,e.areaName,e.floorId,e.floorName,e.labels]),H(Y(this._config?.collection_key)),this._labels.filter_rooms])}_renderIfChanged(){this._signature()!==this._drawn&&this._render()}disconnectedCallback(){this._unfilter?.(),this._unfilter=null}get _labels(){return x(this._hass)}_devices(){return y(this._hass).filter(e=>!e.untracked)}_allDevices(){return y(this._hass)}_optionsFor({kind:e,id:r,name:o},s){let a=new Map,n=!1;for(let c of s)c[r]?a.set(c[r],c[o]??c[r]):n=!0;let i=[...a.entries()].map(([c,l])=>({value:H({kind:e,id:c}),text:l})).sort((c,l)=>c.text.localeCompare(l.text));return n&&i.push({value:H({kind:e,id:null}),text:this._labels.filter_unfiled}),i}_labelOptions(e){let r=et(this._hass);return[...new Set(e.flatMap(s=>s.labels??[]))].map(s=>({value:H({kind:"label",id:s}),text:r[s]??s})).sort((s,a)=>s.text.localeCompare(a.text))}_deviceOptions(){return this._allDevices().map(e=>({value:H({kind:"device",id:e.key}),text:e.name})).sort((e,r)=>e.text.localeCompare(r.text))}_groups(){let e=this._devices(),r=Fs.map(s=>({label:this._labels[s.label],options:this._optionsFor(s,e)})),o=this._labelOptions(e);return o.length&&r.push({label:this._labels.filter_labels,options:o}),r.push({label:this._labels.filter_devices,options:this._deviceOptions()}),r.filter(s=>s.options.length>0)}_render(){let e=this._labels,r=this._devices();this._drawn=this._signature();let o=r.length?this._control(e):`<p class="message">${e.no_devices}</p>`;this.shadowRoot.innerHTML=`
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
    `;let s=this.shadowRoot.querySelector("select");s&&(s.value=H(Y(this._config?.collection_key)),s.addEventListener("change",()=>ot(this._config?.collection_key,$s(s.value))))}_control(e){let r=this._groups().map(o=>`<optgroup label="${g(o.label)}">${o.options.map(s=>`<option value="${g(s.value)}">${g(s.text)}</option>`).join("")}</optgroup>`).join("");return`<div class="body">
      <span class="label">${e.title_filter}</span>
      <select>
        <option value="${H({kind:"all",id:null})}">${g(e.filter_everything)}</option>
        ${r}
      </select>
    </div>`}},Ue=class extends m{},Rs=()=>{_(vr,Ue),f(br,je,{name:"Home Energy Advisor: Filter",description:"Narrow every Home Energy Advisor card on the page to a room, a floor, a label or one device."})};Rs();var wr="hea-self-sufficiency-card",Er=`${wr}-editor`,xr=["energyUsed","energyFromGrid","energyFromGeneration","energyFromBattery"],Is={maximumFractionDigits:0},Ns=.005,Be=class extends w{static titleKey="title_self_sufficiency";static chartTag="ha-gauge";static bearingCard={type:"energy-self-sufficiency-gauge"};static emptyKey="no_energy_in_period";static cardStyle=`
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
      <div class="headline">${this._labels.from_generation}</div>`}_breakdown(e){let{battery:r,grid:o,unaccounted:s}=this._shares();return`<div class="shares">${[{label:"from_battery",value:r},{label:"from_grid",value:o},{label:"unaccounted",value:s}].filter(({label:n,value:i})=>n!=="unaccounted"||i>Ns).map(({label:n,value:i})=>`
        <div class="share">
          <span class="label">${this._labels[n]}</span>
          <span class="value" data-share="${n}">${U(i,e)}</span>
        </div>`).join("")}</div>
      <div class="note">${this._labels.self_sufficiency_note}</div>`}_draw(e){e.min=0,e.max=100,e.value=this._shares().generation*100,e.label="%",e.formatOptions=Is,e.locale=this._hass?.locale}},ze=class extends m{},Ds=()=>{_(Er,ze),f(wr,Be,{name:"Home Energy Advisor: Self-sufficiency",description:"What share of the selected period's energy came from the household's own generation."})};Ds();var kr="hea-sources-card",Sr=`${kr}-editor`,Ms=({energyFromGrid:t,energyUsed:e})=>e>0&&t>=0&&t<=e?t/e:void 0,Ls=[{field:"name",label:"device"},{field:"energyUsed",label:"energy",format:k},{field:"energyFromGrid",label:"grid",format:k},{field:"energyFromGeneration",label:"generation",format:k},{field:"energyFromBattery",label:"battery",format:k},{derive:Ms,label:"from_grid",format:U}],Tr={energy_used:{field:"energyUsed",label:"energy_used"},energy_from_grid:{field:"energyFromGrid",label:"from_grid"},energy_from_generation:{field:"energyFromGeneration",label:"from_generation"},energy_from_battery:{field:"energyFromBattery",label:"from_battery"}},We=class extends M{static titleKey="title_sources";static columns=Ls;static sorts=Tr;static defaultSort="energy_used";static getConfigElement(){return document.createElement(Sr)}},Ke=class extends m{_extraSchema(){return fe(Tr,x(this._hass))}},Gs=()=>{_(Sr,Ke),f(kr,We,{name:"Home Energy Advisor: Energy sources",description:"Grid, generation and battery behind each device's energy over the period."})};Gs();var Ar="hea-totals-card",Or=`${Ar}-editor`,Hs=[{key:"actualCost",label:"paid"},{key:"costAtGridPrice",label:"would_have_paid"},{key:"costSavings",label:"saved"}],Ye=class extends F{static titleKey="title_totals";static cardStyle=`${ie}
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
  `;static getConfigElement(){return document.createElement(Or)}getCardSize(){return 3}_body(e){let r=this._result?.totals;return`<div class="figures">${Hs.map(({key:s,label:a})=>{let n=r?.[s],i=s==="costSavings"?T(n):"",c=i?` ${i}`:"";return`
        <div class="figure">
          <span class="label">${ce(a)}${this._labels[a]}</span>
          <span class="value${c}" data-figure="${s}">${u(n,e)}</span>
          ${this._comparedTo(s,n,e)}
        </div>`}).join("")}</div>`}_comparedTo(e,r,o){let s=this._result?.totals?.before?.[e];if(!Number.isFinite(s)||!Number.isFinite(r))return"";let a=j(e,r-s);return`<span class="${a?`compare ${a}`:"compare"}" data-compare="${e}">${b(this._labels.compared,{change:P(r-s,o),before:u(s,o)})}</span>`}},Ve=class extends m{},Ps=()=>{_(Or,Ve),f(Ar,Ye,{name:"Home Energy Advisor: Totals",description:"What the selected period cost, what it would have cost at grid price, and the difference."})};Ps();
