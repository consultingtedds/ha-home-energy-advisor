var ss=[4,4,0,0],os=[0,0,4,4],ct=t=>t!==null&&typeof t=="object"&&!Array.isArray(t),ns=t=>{let e=ct(t)?t.value:t;return Array.isArray(e)?e[1]:e},we=(t,e)=>{let r=ct(t)?{...t}:{value:t};return{...r,itemStyle:{...r.itemStyle,...e}}},ne=t=>{let e=Math.max(...t.map(({data:s})=>s.length),0),r=t.map(({data:s})=>[...s]);for(let s of as(t))for(let o=0;o<e;o++)is(r,o,s);return t.map((s,o)=>({...s,data:r[o]}))},as=t=>{let e=new Map;return t.forEach((r,s)=>{let o=r.stack??Symbol(s),n=e.get(o);n?n.push(s):e.set(o,[s])}),[...e.values()]},is=(t,e,r)=>{let s=!1,o=!1;for(let n=r.length-1;n>=0;n--){let a=r[n],i=t[a][e];if(i===void 0)continue;let c=ns(i);c?c>0&&!s?(t[a][e]=we(i,{borderRadius:ss}),s=!0):c<0&&!o&&(t[a][e]=we(i,{borderRadius:os}),o=!0):t[a][e]=we(i,{borderWidth:0})}};var lt="_energy",Ee="energy_";var cs=(t,e)=>{let r=t||(e?`${Ee}${e}`:"");return r?r.startsWith(Ee)?`_${r}`:`_${Ee}${r}`:lt},ls=(t,e)=>typeof t=="string"&&t.startsWith(lt)&&e!==null&&typeof e=="object"&&typeof e.subscribe=="function"&&"start"in e,ds=(t=new Date)=>{let e=new Date(t);return e.setDate(e.getDate()-30),e.setHours(0,0,0,0),{start:e,end:t,fallback:!0}},us=t=>{let e=t?.connection;if(!e)return{};let r={};for(let s of Object.keys(e)){let o;try{o=e[s]}catch{continue}ls(s,o)&&(r[s]=o)}return r},hs=(t,e)=>{let r=us(t),s=cs(e,t?.panelUrl);if(r[s])return r[s];let[o]=Object.values(r);return o??null},ps=t=>t?.startCompare&&t?.endCompare?{compare:{start:t.startCompare,end:t.endCompare,mode:t.compareMode}}:{},dt=(t,e,r)=>{let s=null,o=null,n=0,a=t,i=l=>{if(s)return!0;let d=hs(l,e);if(!d)return!1;let h=m=>r({start:d.start,end:d.end,fallback:!1,...ps(m)});return s=d.subscribe(h),h(),!0},c=()=>{o=setTimeout(()=>{o=null,n+=1,!i(a)&&n<40&&c()},250)};return r(ds()),i(t)||c(),{retry:l=>(l&&(a=l),i(a)),unsubscribe:()=>{o&&clearTimeout(o),o=null;try{typeof s=="function"&&s()}catch{}s=null}}};var ae="sensor.home_energy_advisor_devices",ms="home_energy_advisor",ie=t=>{if(t?.states?.[ae])return ae;let e=t?.entities;if(!e)return ae;for(let[r,s]of Object.entries(e))if(s?.platform===ms&&Array.isArray(t?.states?.[r]?.attributes?.devices))return r;return ae},g=(t,e=void 0)=>{let r=t?.states?.[e??ie(t)]?.attributes?.devices;return Array.isArray(r)?r.filter(s=>s?.key).map(pt):[]},H=(t,e=void 0)=>{let r=t?.states?.[e??ie(t)]?.attributes?.whole_home;return r?.key?pt(r):null},ut=(t,e=void 0)=>{let r=t?.states?.[e??ie(t)]?.attributes?.settled_until;if(typeof r!="string")return null;let s=new Date(r);return Number.isNaN(s.getTime())?null:s},ht=(t,e=void 0)=>{let r=t?.states?.[e??ie(t)]?.attributes?.labels;return r&&typeof r=="object"?r:{}},pt=t=>({key:t.key,name:t.name||t.key,deviceId:t.device_id??null,untracked:!!t.untracked,statistics:t.statistics??{},areaId:t.area_id??null,areaName:t.area_name??null,floorId:t.floor_id??null,floorName:t.floor_name??null,upstream:t.upstream??null,gross:!!t.gross,labels:Array.isArray(t.labels)?t.labels:[]});var mt=Object.freeze({kind:"all",id:null}),fs={area:"areaId",floor:"floorId"},Se=new Map,ke=t=>(Se.has(t)||Se.set(t,{filter:mt,listeners:new Set}),Se.get(t)),Z=t=>ke(t).filter,ce=(t,e)=>{let{listeners:r}=ke(t);return r.add(e),()=>r.delete(e)},ft=(t,e)=>{let r=ke(t),s={kind:e?.kind??"all",id:e?.id??null};if(!(s.kind===r.filter.kind&&s.id===r.filter.id)){r.filter=s;for(let o of r.listeners)try{o(s)}catch(n){console.warn("home-energy-advisor: a card could not follow the filter",n)}}},_t=(t,e)=>{let{kind:r,id:s}=e??mt;if(r==="all")return!0;if(r==="device")return t.key===s;if(t.untracked)return!1;if(r==="label")return(t.labels??[]).includes(s);let o=fs[r];return o?(t[o]??null)===s:!0};var _s={day:"numeric",month:"short",year:"numeric"},le=t=>({language:t?.locale?.language||void 0,currency:t?.config?.currency||void 0,timeFormat:t?.locale?.time_format||void 0,timeZone:t?.locale?.time_zone==="server"?t?.config?.time_zone:void 0}),gs=({timeFormat:t,language:e})=>{if(t==="language"||t==="system"||!t){let r=t==="system"?void 0:e;return new Date("January 1, 2023 22:00:00").toLocaleString(r).includes("10")}return t==="12"},gt=(t,e)=>new Intl.DateTimeFormat(e.language,{hour:"numeric",minute:"2-digit",hourCycle:gs(e)?"h12":"h23",timeZone:e.timeZone}).format(t),ys=(t,e)=>new Intl.DateTimeFormat(e.language,{weekday:"short",month:"short",day:"numeric",timeZone:e.timeZone}).format(t),bs={hour:3600*1e3},yt=(t,e,r)=>{let s=bs[e];if(!s)return ys(t,r);let o=new Date(t.getTime()+s);return`${gt(t,r)} \u2013 ${gt(o,r)}`},u=(t,{language:e,currency:r})=>typeof t!="number"||!Number.isFinite(t)?"-":new Intl.NumberFormat(e,{...bt(r),signDisplay:"negative"}).format(t),bt=t=>t?{style:"currency",currency:t}:{minimumFractionDigits:2,maximumFractionDigits:2},vt=(t,{language:e,currency:r}={})=>{let o=10**new Intl.NumberFormat(e,bt(r)).resolvedOptions().maximumFractionDigits;return Math.round(t*o)/o},j=(t,{language:e,currency:r})=>{if(typeof t!="number"||!Number.isFinite(t))return"-";let s=r?{style:"currency",currency:r,signDisplay:"exceptZero"}:{minimumFractionDigits:2,maximumFractionDigits:2,signDisplay:"exceptZero"};return new Intl.NumberFormat(e,s).format(t)},vs=new Set(["actualCost","costAtGridPrice","energyUsed"]),xs=new Set(["costSavings"]),E=(t,e)=>{if(typeof t!="number"||!Number.isFinite(t))return"";let r=vt(t,e);return r===0?"":r>0?"gain":"loss"},ws=new Set(["actualCost","costAtGridPrice","costSavings"]),B=(t,e,r)=>{if(typeof e!="number"||!Number.isFinite(e))return"";let s=ws.has(t)?vt(e,r):e;return s===0?"":vs.has(t)?s<0?"gain":"loss":xs.has(t)?s>0?"gain":"loss":""},W=(t,e)=>{if(!Array.isArray(t))return"-";let[r,s]=t;if(![r,s].every(a=>Number.isFinite(a)))return"-";if(r===s)return u(r,e);let[o,n]=r<=s?[r,s]:[s,r];return`${u(o,e)} - ${u(n,e)}`},$=(t,{language:e})=>typeof t!="number"||!Number.isFinite(t)?"-":`${new Intl.NumberFormat(e,{maximumFractionDigits:1}).format(t)} kWh`,xt={EUR:{symbol:"c",per:100},USD:{symbol:"\xA2",per:100},GBP:{symbol:"p",per:100}},X=(t,{language:e})=>typeof t!="number"||!Number.isFinite(t)?"-":new Intl.NumberFormat(e,{minimumFractionDigits:t===0?0:2,maximumFractionDigits:2}).format(t),Q=({language:t,currency:e})=>e?wt(t,e):"",wt=(t,e)=>new Intl.NumberFormat(t,{style:"currency",currency:e}).formatToParts(0).find(r=>r.type==="currency")?.value??"",Et=({language:t,currency:e})=>{if(!e)return"/kWh";let r=xt[e];return`${r?r.symbol:wt(t,e)}/kWh`},St=(t,{language:e,currency:r})=>{if(typeof t!="number"||!Number.isFinite(t))return"-";let s=r?xt[r]:void 0;return new Intl.NumberFormat(e,{minimumFractionDigits:s?1:0,maximumFractionDigits:s?2:3}).format(s?t*s.per:t)},U=(t,{language:e})=>typeof t!="number"||!Number.isFinite(t)?"-":new Intl.NumberFormat(e,{style:"percent",maximumFractionDigits:0}).format(t),b=t=>String(t).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#39;"),J=(t,{language:e})=>t?new Intl.DateTimeFormat(e,_s).formatRange(t.start,t.end):"";var At="common",Ot="home_energy_advisor",kt=`component.${Ot}.${At}.card_`,Oe=Object.freeze({paid:"Paid",would_have_paid:"Would have paid",saved:"Saved",lost:"Lost",range_column:"Paid (min-max)",range_note:"Paid (min-max) is the widest range these readings allow, not a typical error: a meter that reports every 30-90 minutes leaves the exact moment of use unknown.",range_whole_home:"What you paid could honestly sit between {range} - the widest these readings allow, not a typical error.",range_device:"What you paid could be between {range}.",range_note_rollover:"Hover over or tap a figure in Paid to see the range it could honestly have been. That range is the widest these readings allow, not a typical error: a meter that reports every 30-90 minutes leaves the exact moment of use unknown.",forgone_column:"Could have earned",forgone_note:"Could have earned is what the generation each device used could have earned had you exported it instead, at your export rate at the time. It is money you did not receive, not money you paid, and it is not part of Paid.",forgone_hidden_note:"Could have earned, what the generation each device used could have earned had you exported it instead, is shown on a wider screen.",compared:"{change} vs {before}",compared_period:"{period} vs {compared}",saved_share:"{percent} of what you would have paid was saved.",lost_share:"{percent} more was paid than the grid would have cost.",change:"Change",compared_series:"Earlier period",device:"Device",energy:"Energy",rate:"Rate",total:"Total",grid:"Grid",generation:"Generation",battery:"Battery",from_grid:"From the grid",from_generation:"From generation",from_battery:"From the battery",from_battery_grid:"From battery (grid)",including_stored_solar:"including stored solar",energy_used:"Energy used",unaccounted:"Unaccounted",self_sufficiency_note:"Solar stored in the battery counts as your own. Battery energy charged from the grid does not, and is shown on its own.",household:"Household",generation_saved:"Generation saved",battery_saved:"Battery saved",exports_earned:"Exports earned",installation_note:"For the whole home: your own generation, your battery and your exports, measured against your current tariff. What the battery lost is taken off what it saved.",no_installation:"There is no generation or battery here, so nothing for an installation to have earned.",title_installation:"What your installation earned",title_plans:"Compare tariff plans",plans_your_plan:"Your plan",plans_cheapest:"Cheapest",plans_energy:"Energy",plans_export:"Export",plans_daily:"Daily charges",plans_less:"{amount} less than your plan",plans_more:"{amount} more than your plan",plans_same:"The same as your plan",plans_incomplete:"Not every hour has a price, so it cannot be compared. Edit the plan to finish its bands.",plans_note:"For the whole home: each plan priced at the electricity you actually imported and exported, as if your battery had run the same way. Prices are compared as you entered them.",plans_no_readings:"Your grid meters recorded nothing in this period, so only the daily charges are shown.",plans_no_current:"Mark one plan as the one you are on to see how the others compare.",no_plans:"No tariff plans yet. Add one from the Home Energy Advisor integration, with Add tariff plan.",title_totals:"Cost summary",title_devices:"Cost by device",title_device_costs:"What each device cost",title_cost_over_time:"Cost over time",title_sources:"Where the energy came from",title_self_sufficiency:"Self-sufficiency",title_distribution:"Where the cost went",title_distribution_energy:"Where the energy went",no_devices:"No devices are being tracked yet.",no_devices_in_filter:"No tracked device matches what the page is showing.",title_filter:"Show",filter_everything:"Everything",filter_rooms:"Rooms",filter_floors:"Floors",filter_labels:"Labels",filter_devices:"Devices",filter_unfiled:"Not in one",device_untracked:"Untracked",hourly_shape_estimate:"One device's hourly shape is an estimate: each meter reading is spread across the hours it spanned, so cost may not land in the hour the energy was used.",still_accruing:"The last interval is still being counted, so its bar will grow. Figures are complete about twenty minutes behind the clock, which is how long meters are given to report.",statistics_failed:"Statistics could not be loaded.",no_picker:"Add an Energy date picker card to choose the range.",chart_not_loaded:"Home Assistant's chart component is not loaded. Adding any energy or statistics card to this dashboard will load it.",no_cost_in_period:"No cost recorded in this period.",no_energy_in_period:"No energy recorded in this period.",editor_title:"Title",editor_collection_key:"Energy period (collection key)",editor_devices:"Devices (all, if none are chosen)",editor_sort_by:"Order by",editor_layout:"Layout",editor_metric:"Measure by",editor_group_by_floor:"Group by floor",editor_group_by_area:"Group by area",editor_range:"Show the cost range as",editor_range_auto:"Automatic: a column where there is room",editor_range_rollover:"A rollover on Paid",editor_range_column:"Its own column"}),Ae=new Map,Tt=new Map,Ct=t=>t?.locale?.language||t?.language||"en",S=t=>{let e=Ct(t);return Ae.has(e)||Ae.set(e,Es(t,e).then(r=>(Tt.set(e,r),r))),Ae.get(e)},Es=async(t,e)=>{try{let{resources:r}=await t.callWS({type:"frontend/get_translations",language:e,category:At,integration:[Ot]});return Object.freeze({...Oe,...Ss(r)})}catch(r){return console.warn("home-energy-advisor: falling back to English labels",r),Oe}},k=t=>Tt.get(Ct(t))??Oe,Ss=t=>Object.fromEntries(Object.entries(t??{}).filter(([e,r])=>e.startsWith(kt)&&r).map(([e,r])=>[e.slice(kt.length),r])),v=(t,e)=>Object.entries(e).reduce((r,[s,o])=>r.replaceAll(`{${s}}`,o),t);var x=Object.freeze({energyUsed:"energy_used",actualCost:"actual_cost",costAtGridPrice:"cost_at_grid_price",energyFromGrid:"energy_from_grid",energyFromGeneration:"energy_from_generation",energyFromBattery:"energy_from_battery",energyFromBatterySolar:"energy_from_battery_solar",forgoneExport:"forgone_export"}),R=Object.freeze({costFloor:"lowest_possible_cost",costCeiling:"highest_possible_cost"}),Te=()=>Object.fromEntries(Object.keys(x).map(t=>[t,0])),Rt=1440*60*1e3,It={hour:3600*1e3,day:Rt},ks=2,z=(t,e)=>t?.statistics?.[e],ee=t=>x.costAtGridPrice in(t?.statistics??{}),Nt=(t,e,r,s=!1)=>e==="costAtGridPrice"&&!ee(t)?z(t,x.actualCost):e==="energyFromGrid"&&s?z(t,x.energyUsed):z(t,r),As=t=>[x.energyFromGrid,x.energyFromGeneration,x.energyFromBattery].some(e=>e in(t?.statistics??{})),Os=t=>t.length>0&&!t.some(As),Ce=(t,e=[])=>{let r=g(t);return Os(r.length?r:e)},Ts=(t,e)=>{let r=t.flatMap(s=>[...Object.values(x),...Object.values(R)].map(o=>z(s,o)).filter(Boolean));return!e?.statistics||t.length===0?r:[...r,...Object.values(R).map(s=>z(e,s)).filter(Boolean)]},Dt=(t,e)=>{if(!e)return t;let r=new Map(e.devices.map(s=>[s.key,s]));return{...t,totals:{...t.totals,before:e.totals},devices:t.devices.map(s=>({...s,before:r.get(s.key)})),seriesBefore:Cs(e.series,t.period,e.period)}},Cs=(t,e,r)=>{if(!t?.length)return;let s=e.start.getTime()-r.start.getTime();return t.map(o=>({...o,start:new Date(o.start.getTime()+s),actualStart:o.start}))},O=({start:t,end:e})=>e-t>ks*Rt?"day":"hour",$t=(t,e,r)=>{if(e!=="day")return new Date(t.getTime()+r*It.hour);let s=new Date(t);return s.setDate(s.getDate()+r),s},Mt=(t,e)=>{if(!t.length||!e)return t;let r=O(e),s=new Map(t.map(a=>[a.start.getTime(),a])),o=t[0].start,n=[];for(let a=0;;a--){let i=$t(o,r,a);if(i.getTime()<e.start.getTime())break;n.push(s.get(i.getTime())??Ft(i))}n.reverse();for(let a=1;;a++){let i=$t(o,r,a);if(i.getTime()>=e.end.getTime())break;n.push(s.get(i.getTime())??Ft(i))}return n},Ft=t=>({...Te(),start:t,costSavings:0,accruing:!1}),$e=async(t,e,r,s,o=null)=>{let n=Ts(e,s),a=n.length?await t.callWS({type:"recorder/statistics_during_period",start_time:r.start.toISOString(),end_time:r.end.toISOString(),statistic_ids:n,period:O(r),types:["change"]}):{},i=Ce(t,e),c=Rs(e.map(l=>Fs(l,a,r,i)));return{period:r,gridOnly:i,devices:c,totals:Ns(c),wholeHome:Lt(s,a,r),series:$s(e,a,r,o,i)}},Lt=(t,e,r)=>{if(!t)return;let s={};for(let[o,n]of Object.entries(R)){let a=e?.[z(t,n)];if(!Array.isArray(a))return;s[o]=Pt(a,r)}return s},$s=(t,e,r,s,o)=>{let n=new Map,a=new Set(t.filter(c=>c.gross).map(c=>c.key));for(let c of t.filter(l=>!a.has(l.upstream)))for(let[l,d]of Object.entries(x)){let h=e?.[Nt(c,l,d,o)];for(let m of Gt(h,r)){let w=n.get(m.start)??Te();w[l]+=m.change,n.set(m.start,w)}}let i=It[O(r)]??0;return[...n.entries()].sort(([c],[l])=>c-l).map(([c,l])=>({...l,start:new Date(c),costSavings:l.costAtGridPrice-l.actualCost,accruing:s?c+i>s.getTime():!1}))},Fs=(t,e,r,s)=>{let o=Object.fromEntries(Object.entries(x).map(([n,a])=>[n,Pt(e?.[Nt(t,n,a,s)],r)]));return{...t,...o,...Lt(t,e,r),costSavings:o.costAtGridPrice-o.actualCost}},Rs=t=>{let e=new Map;for(let r of t)r.upstream&&e.set(r.upstream,[...e.get(r.upstream)??[],r]);return t.map(r=>{if(!r.gross)return r;let s={...r};for(let o of Object.keys(x)){let n=(e.get(r.key)??[]).reduce((a,i)=>a-i[o],r[o]);s[o]=Math.abs(n)<Is(o)?0:n}return s.costSavings=s.costAtGridPrice-s.actualCost,s})},Is=t=>t.startsWith("energy")?5e-4:.005,Gt=(t,{start:e,end:r})=>{if(!Array.isArray(t))return[];let s=[];for(let o of t){let n=new Date(o.start).getTime();n<e.getTime()||n>=r.getTime()||typeof o.change=="number"&&s.push({start:n,change:o.change})}return s},Pt=(t,e)=>Gt(t,e).reduce((r,s)=>r+s.change,0),Ns=t=>({...t.reduce((r,s)=>{for(let o of Object.keys(r))r[o]+=s[o];return r},{...Te(),costSavings:0}),...Ds(t)}),Ds=t=>{let e=Object.keys(R);return!t.length||!t.every(r=>e.every(s=>s in r))?{}:Object.fromEntries(e.map(r=>[r,t.reduce((s,o)=>s+o[r],0)]))};var Ms=`
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
`,Ls=`
  .loss { color: var(--error-color, #db4437); }
  .gain { color: var(--success-color, #4caf50); }
`,N="(max-width: 767px)",A=class extends HTMLElement{static cardStyle="";static narrowQuery="";static titleKey="";_titleKey(){return this.constructor.titleKey}get _labels(){return k(this._hass)}constructor(){super(),this.attachShadow({mode:"open"}),this._state="loading",this._request=0}setConfig(e){if(e.devices!==void 0&&!Array.isArray(e.devices))throw new Error("`devices` must be a list of device keys");this._config=e,this._render()}set hass(e){this._hass=e,this._subscription?this._subscription.retry(e):this._subscribe(),this._refetchIfDevicesChanged()}connectedCallback(){this._render(),this._hass&&!this._subscription&&this._subscribe(),this._watchScreen()}disconnectedCallback(){this._subscription?.unsubscribe(),this._subscription=null,this._unfilter?.(),this._unfilter=null,this._screen?.removeEventListener?.("change",this._onScreenChange),this._screen=null}_watchScreen(){let{narrowQuery:e}=this.constructor;!e||this._screen||(this._screen=globalThis.matchMedia?.(e),this._onScreenChange??=()=>this._render(),this._screen?.addEventListener?.("change",this._onScreenChange))}_isNarrow(){return!!globalThis.matchMedia?.(N)?.matches}_subscribe(){this._subscription=dt(this._hass,this._config?.collection_key,e=>{this._period=e,this._scheduleFetch()}),this._unfilter=ce(this._config?.collection_key,()=>this._scheduleFetch())}_scheduleFetch(){this._fetchPending||(this._fetchPending=!0,queueMicrotask(()=>{this._fetchPending=!1,this._fetch()}))}_refetchIfDevicesChanged(){let e=this._devices().map(r=>r.key).join(",");e!==this._deviceKeys&&(this._deviceKeys=e,this._period&&this._scheduleFetch())}_devices(){let e=g(this._hass),r=this._config?.devices,s=r?e.filter(n=>r.includes(n.key)):e,o=this._filter();return s.filter(n=>_t(n,o))}_filter(){return Z(this._config?.collection_key)}_isFiltered(){return!!this._config?.devices||this._filter().kind!=="all"}async _fetch(){if(!this._hass||!this._period)return;let e=this._devices(),r=++this._request;if(await S(this._hass),e.length===0){this._state="empty",this._render();return}let s=this._isFiltered()?void 0:H(this._hass);try{let o=ut(this._hass),[n,a]=await Promise.all([$e(this._hass,e,this._period,s,o),this._period.compare?$e(this._hass,e,this._period.compare,s):void 0]);if(r!==this._request)return;this._result=Dt(n,a),this._state="ready"}catch(o){if(r!==this._request)return;this._state="error",console.error(`${this.localName}: could not load statistics`,o)}this._render()}_render(){let e=le(this._hass);this.shadowRoot.innerHTML=`
      <style>${Ms}${this.constructor.cardStyle}${Ls}</style>
      <ha-card>
        <div class="body" data-state="${this._state}">${this._content(e)}</div>
      </ha-card>
    `;let r=this._config?.title??this._labels[this._titleKey()];r&&this._writeHeader(r,e),this._afterRender()}_writeHeader(e,r){let s=this.shadowRoot.querySelector("ha-card"),o=this._headerChip(r);if(o===void 0){s.setAttribute("header",e);return}s.insertAdjacentHTML("afterbegin",`<div class="card-header" style="display: flex; justify-content: space-between;
         align-items: center; gap: var(--hea-space-s); padding-bottom: 0;">
        <span class="title">${b(e)}</span>
        <span class="chip">${b(o)}</span>
      </div>`)}_headerChip(){}_afterRender(){}_content(e){return this._state==="empty"?`<p class="message">${this._labels.no_devices}</p>`:this._state==="error"?`<p class="message">${this._labels.statistics_failed}</p>`:`${this._body(e)}${this._caption(e)}`}_caption(e){let r=this._period?.fallback?`<div class="hint">${this._labels.no_picker}</div>`:"";return`<div class="period">${this._periodLabel(e)}</div>${r}`}_periodLabel(e){let r=J(this._period,e),s=this._period?.compare;return s?v(this._labels.compared_period,{period:r,compared:J(s,e)}):r}},f=(t,e,{name:r,description:s})=>{customElements.get(t)||customElements.define(t,e),globalThis.customCards=globalThis.customCards??[],globalThis.customCards.some(o=>o.type===t)||globalThis.customCards.push({type:t,name:r,description:s})};var Gs={title:"editor_title",collection_key:"editor_collection_key",devices:"editor_devices",sort_by:"editor_sort_by",layout:"editor_layout",metric:"editor_metric",group_by_floor:"editor_group_by_floor",group_by_area:"editor_group_by_area",range:"editor_range"},p=class extends HTMLElement{constructor(){super(),this.attachShadow({mode:"open"})}setConfig(e){this._config=e,this._render()}set hass(e){this._hass=e,this._render(),S(e).then(()=>this._render())}_extraSchema(){return[]}_render(){if(!this._config)return;let e=this.shadowRoot.querySelector("ha-form");e||(e=document.createElement("ha-form"),e.computeLabel=r=>k(this._hass)[Gs[r.name]]??r.name,e.addEventListener("value-changed",r=>this._report(r.detail.value)),this.shadowRoot.append(e)),e.hass=this._hass,e.data=this._config,e.schema=this._schema()}_schema(){return[{name:"title",selector:{text:{}}},{name:"collection_key",selector:{text:{}}},{name:"devices",selector:{select:{multiple:!0,mode:"list",options:g(this._hass).map(e=>({value:e.key,label:e.name}))}}},...this._extraSchema()]}_report(e){this.dispatchEvent(new CustomEvent("config-changed",{detail:{config:Ps({...this._config,...e})},bubbles:!0,composed:!0}))}},Ps=t=>Object.fromEntries(Object.entries(t).filter(([,e])=>e!==""&&e!==void 0&&e!==null&&!(Array.isArray(e)&&e.length===0))),_=(t,e)=>{customElements.get(t)||customElements.define(t,e)};var T=class extends A{static chartTag="ha-chart-base";static bearingCard={type:"statistics-graph",entities:[]};static emptyKey="no_cost_in_period";static chartHeight="clamp(320px, 40vw, 480px)";static cardStyle=`
    ha-chart-base { display: block; --chart-max-height: none; }
  `;constructor(){super(),this._chartReady=!!customElements.get(this.constructor.chartTag)}getCardSize(){return 6}connectedCallback(){super.connectedCallback(),this._chartReady||this._loadChartComponent()}async _loadChartComponent(){let{chartTag:e,bearingCard:r}=this.constructor;customElements.whenDefined(e).then(()=>{this._chartReady=!0,this._render()});try{await(await globalThis.loadCardHelpers?.())?.createCardElement(r)}catch(s){console.warn(`${e}: could not be loaded`,s)}}_isEmpty(){return(this._result?.series??[]).length===0}_body(){return this._chartReady?this._isEmpty()?`<p class="message">${this._labels[this._emptyKey()]}</p>`:this._chartMarkup():`<p class="message">${this._labels.chart_not_loaded}</p>`}_emptyKey(){return this.constructor.emptyKey}_chartMarkup(){return'<ha-chart-base chart-type="bar"></ha-chart-base>'}_afterRender(){let e=this.shadowRoot.querySelector(this.constructor.chartTag);e&&(e.hass=this._hass,this._draw(e))}_chartHeight(){return this.constructor.chartHeight}_draw(e){e.height=this._chartHeight(),e.data=this._series(),e.options=this._options(this._chartLocale())}_chartLocale(){return le(this._hass)}_colour({variable:e,fallback:r}){return getComputedStyle(this).getPropertyValue(e).trim()||r}};var Hs=/^#([\da-f]{3}|[\da-f]{6})$/i,js=/^rgba?\(([^)]+)\)$/i,Fe=t=>{let e=Hs.exec(String(t).trim());if(e){let o=e[1];return(o.length===3?[...o].map(a=>a+a):[0,2,4].map(a=>o.slice(a,a+2))).map(a=>Number.parseInt(a,16))}let r=js.exec(String(t).trim());if(!r)return;let s=r[1].split(/[\s,/]+/).filter(Boolean).slice(0,3).map(Number);return s.length===3&&s.every(Number.isFinite)?s:void 0},F=(t,e)=>{let r=Fe(String(t).trim());return r?`rgba(${r.join(", ")}, ${e})`:t},Bs=([t,e,r])=>(.2126*t+.7152*e+.0722*r)/255,de=t=>{let e=Fe(Ws(t));return e?Bs(e)>.5:!1},Ws=t=>{let e=[t,t?.ownerDocument?.documentElement].filter(Boolean);for(let r of e){let s=getComputedStyle(r),o=s.getPropertyValue("--primary-text-color").trim()||s.color;if(Fe(o))return o}return""};var Ht=Object.freeze({variable:"--primary-color",fallback:"#03a9f4"}),jt=Object.freeze({variable:"--success-color",fallback:"#4caf50"}),Us=Object.freeze({paid:"paid",would_have_paid:"would-have-paid",saved:"saved"}),ue=`
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
`,he=t=>{let e=typeof t=="string"?Us[t]:void 0;return e?`<span class="swatch ${e}" aria-hidden="true"></span>`:""};var I=(t,e,r,{bold:s=!1}={})=>{let o=document.createElement("div");o.style.display="flex",o.style.justifyContent="space-between",o.style.gap="16px",s&&(o.style.fontWeight="bold");let n=document.createElement("span");n.textContent=t;let a=document.createElement("span");return a.textContent=e,a.style.fontVariantNumeric="tabular-nums",r&&(a.style.color=r),o.append(n,a),o},zs=t=>{let e=document.createElement("span");return e.style.display="inline-block",e.style.width="10px",e.style.height="10px",e.style.borderRadius="10px",e.style.marginInlineEnd="4px",e.style.verticalAlign="middle",e.style.backgroundColor=t,e},Bt=(t,e,r,s)=>{let o=I(e,r,s);return o.firstChild.prepend(zs(t)),o},pe=t=>{let e=document.createElement("div");return e.textContent=t,e.style.fontWeight="bold",e.style.textAlign="center",e.style.marginBottom="4px",e},Wt=t=>{let e=document.createElement("div");return e.textContent=t,e.style.marginTop="4px",e.style.maxWidth="260px",e.style.whiteSpace="normal",e.style.opacity="0.7",e};var Yt="hea-cost-over-time-card",qt=`${Yt}-editor`,Ks={hour:3600*1e3,day:1440*60*1e3},Ys=50,qs=.5,Vs=(t,e)=>{if(!t.length||!e)return 0;let r=Ks[O(e)]??0,s=t.length>=2?t[1].start.getTime()-t[0].start.getTime():void 0;return(s?Math.min(s,r):r)/2},D={paid:{id:"paid",name:"paid",...Ht},saved:{id:"saved",name:"saved",...jt}},Vt={variable:"--error-color",fallback:"#db4437"},Zs={gain:{variable:"--success-color",fallback:"#4caf50"},loss:Vt},Re=t=>t.value?.[1]??0,Xs=t=>t.value?.[2],Qs=.45,me={id:"before",name:"compared_series",variable:"--secondary-text-color",fallback:"#727272"},Ie=class extends T{static titleKey="title_cost_over_time";static getConfigElement(){return document.createElement(qt)}_series(){let e=Mt(this._result?.series??[],this._result?.period),r=this._colour(Vt),s=this._labels,o=this._result?.seriesBefore,n=Vs(e,this._result?.period),a={...Kt(D.paid,this._colour(D.paid),s),data:e.map(c=>Ut(c,zt(c,c.actualCost,n)))},i={...Kt(D.saved,this._colour(D.saved),s),data:e.map(c=>{let l=zt(c,c.costSavings,n),d=c.costSavings<0?Zt(r):void 0;return Ut(c,l,d)})};return[...ne(this._result?.gridOnly?[a]:[a,i]),...o?.length?[{id:me.id,name:s[me.name],type:"line",symbol:"none",lineStyle:{type:"dashed",width:2},itemStyle:{color:this._colour(me)},data:o.map(c=>[c.start.getTime()+n,c.costAtGridPrice])}]:[]]}_caption(e){return`${super._caption(e)}${this._stillAccruingNote()}`+this._accrualNote()}_stillAccruingNote(){return(this._result?.series??[]).some(e=>e.accruing)?`<div class="hint">${this._labels.still_accruing}</div>`:""}_accrualNote(){return this._devices().length!==1||!this._period||O(this._period)!=="hour"?"":`<div class="hint">${this._labels.hourly_shape_estimate}</div>`}_tooltipFor(e,r){let s=(Array.isArray(e)?e:[e]).filter(c=>c.componentSubType==="bar"),o=s.filter(c=>Re(c)!==0);if(!o.length)return;let n=this._bucketAt(s.map(Xs).find(c=>c!==void 0)),a=document.createElement("div");a.append(pe(this._spanOf(n,r)));for(let c of o)a.append(this._tooltipRowFor(c,r));let i=s.reduce((c,l)=>c+Re(l),0);return o.length>1&&a.append(I(this._labels.would_have_paid,u(i,r),void 0,{bold:!0})),n?.accruing&&a.append(Wt(this._labels.still_accruing)),a}_tooltipRowFor(e,r){let s=Re(e),o=e.seriesId===D.saved.id?E(s,r):"",n=o==="loss"?this._labels.lost:e.seriesName;return Bt(e.color,n,u(s,r),o?this._colour(Zs[o]):void 0)}_bucketAt(e){if(e!==void 0)return(this._result?.series??[]).find(r=>r.start.getTime()===e)}_spanOf(e,r){return!e||!this._period?"":yt(e.start,O(this._period),r)}_headerChip(e){let r=this._result?.totals?.actualCost;return Number.isFinite(r)&&!this._isEmpty()?u(r,e):""}_axisBounds(){if(!this._period)return{};let{start:e,end:r}=this._period,s=new Date(r.getTime()-1);return O(this._period)==="hour"?s.setMinutes(30,0,0):(s.getHours()===0&&s.setHours(s.getHours()-1),s.setHours(0,0,0,0)),{min:e.getTime(),max:s.getTime()}}_options(e){let r=this._labels;return{xAxis:{type:"time",...this._axisBounds()},grid:{top:15,bottom:0,left:1,right:1,containLabel:!0},yAxis:{type:"value",name:Q(e),nameGap:2,nameTextStyle:{align:"left"},boundaryGap:[0,0],splitNumber:5,splitLine:{show:!0},axisLabel:{formatter:s=>X(s,e),hideOverlap:!0}},tooltip:{trigger:"axis",axisPointer:{type:"shadow"},formatter:s=>this._tooltipFor(s,e)},legend:{show:!0,type:"custom",data:[D.paid,D.saved,...this._result?.seriesBefore?.length?[me]:[]].map(s=>({id:s.id,name:r[s.name],itemStyle:{color:this._colour(s)}}))}}}},Ut=(t,e,r=void 0)=>t.accruing?{value:e,itemStyle:{...r,opacity:Qs}}:r?{value:e,itemStyle:r}:e,zt=(t,e,r)=>[t.start.getTime()+r,e,t.start.getTime()],Kt=({id:t,name:e},r,s)=>({id:t,name:s[e],type:"bar",stack:"cost",barMaxWidth:Ys,itemStyle:Zt(r)}),Zt=t=>({color:F(t,qs),borderColor:t,borderWidth:1}),Ne=class extends p{},Js=()=>{_(qt,Ne),f(Yt,Ie,{name:"Home Energy Advisor: Cost over time",description:"What the period cost, stacked against what it would have cost at grid price."})};Js();var fe=(t,e)=>{let r=e?.statistics?.cost_savings;return!!(r&&t?.states?.[r])},Xt=(t,e)=>({costSavings:t?.statistics?.cost_savings,batterySavings:t?.statistics?.battery_savings,lossesPaid:(e??[]).filter(r=>!r.untracked&&!r.upstream).filter(r=>!ee(r)).map(r=>r.statistics?.actual_cost).filter(Boolean)}),Qt=(t,e)=>{let r=e?.cost_sensors??{},s=[];for(let o of t?.energy_sources??[]){if(o?.type!=="grid")continue;let n=Array.isArray(o.flow_to)?o.flow_to:[o];for(let a of n){let i=a?.stat_compensation||a?.stat_energy_to&&r[a.stat_energy_to];i&&!s.includes(i)&&s.push(i)}}return s},Jt=t=>[t.costSavings,t.batterySavings,...t.lossesPaid??[],...t.exportsEarned??[]].filter(Boolean),er=(t,e,r)=>{let s=m=>eo(t?.[m],r),o=s(e.costSavings),n=!!e.batterySavings,a=n?s(e.batterySavings):0,i=(e.lossesPaid??[]).reduce((m,w)=>m+s(w),0),c=e.exportsEarned??[],l=o-a,d=n?a-i:void 0,h=c.length?c.reduce((m,w)=>m+s(w),0):void 0;return{generationSaved:l,batterySaved:d,exportsEarned:h,total:l+(d??0)+(h??0)}},eo=(t,{start:e,end:r})=>{if(!Array.isArray(t))return 0;let s=0;for(let o of t){let n=new Date(o.start).getTime();n<e.getTime()||n>=r.getTime()||typeof o.change=="number"&&(s+=o.change)}return s};var Le="hea",nr="Home Energy Advisor",to="mdi:home-lightning-bolt",tr=`ll-strategy-dashboard-${Le}`,rr=`ll-strategy-view-${Le}`,K=4,ro=[{type:"custom:hea-totals-card"},{type:"custom:hea-devices-card",sort_by:"actual_cost"}],so=[{type:"custom:hea-cost-over-time-card"},{type:"custom:hea-sources-card",sort_by:"energy_used"}],sr=[{type:"custom:hea-device-costs-card"},{type:"custom:hea-distribution-card"},{type:"custom:hea-self-sufficiency-card"}],oo={type:"custom:hea-installation-card"},no=new Set(["custom:hea-sources-card","custom:hea-self-sufficiency-card"]),or=(t,e)=>e?t.filter(r=>!no.has(r.type)):t,ao=t=>fe(t,H(t))?[...sr,oo]:sr,io=t=>({...t,grid_options:{columns:"full",rows:"auto"}}),_e=(t,e)=>({type:"grid",column_span:e,cards:t.map(io)}),co=()=>({card:{type:"horizontal-stack",cards:[{type:"energy-date-selection",vertical_opening_direction:"up"},{type:"custom:hea-filter-card"}]},max_width:1600}),lo=t=>({type:"sections",max_columns:K,sections:[{type:"grid",cards:[{type:"markdown",content:k(t).no_devices}]}]}),uo={type:"custom:hea-plans-card"},ho=async t=>{try{let e=await t.callWS({type:"home_energy_advisor/list_plans"});return Array.isArray(e?.plans)&&e.plans.length>0}catch{return!1}},po=(t,e)=>{if(g(t).length===0)return lo(t);let r=Ce(t);return{type:"sections",max_columns:K,sections:[_e(ro,K),_e(or(so,r),K/2),_e(or(ao(t),r),K/2),...e?[_e([uo],K)]:[]],footer:co()}},ar=async t=>{let[,e]=await Promise.all([S(t),ho(t)]);return po(t,e)},De=class extends HTMLElement{static async generate(e,r){return{views:[await ar(r)]}}static noEditor=!0;static getCreateSuggestions(){return{title:nr,icon:to}}},Me=class extends HTMLElement{static async generate(e,r){return ar(r)}},mo=t=>{globalThis.customStrategies=globalThis.customStrategies??[],globalThis.customStrategies.some(e=>e.type===t.type)||globalThis.customStrategies.push(t)},fo=()=>{customElements.get(tr)||customElements.define(tr,De),customElements.get(rr)||customElements.define(rr,Me),mo({type:Le,strategyType:"dashboard",name:nr,description:"What each device cost to run, and what solar and the battery saved."})};fo();var Ge=Object.keys(x),_o=Object.keys(R),ir=t=>{let e=new Map;for(let r of t){if(!r.upstream)continue;let s=e.get(r.upstream);s?s.push(r):e.set(r.upstream,[r])}return e},Pe=(t,e)=>({...t,key:`${t.key}${go}`,name:`${t.name} ${e.device_untracked}`,upstream:t.key,untracked:!1,gross:!1,residualOf:t.key}),go="__untracked",cr=(t,e)=>t.gross&&Ge.every(r=>!t[r])?[]:[Pe(t,e)],yo=t=>{let e=Object.fromEntries(Ge.map(r=>[r,0]));for(let r of t)for(let s of Ge)e[s]+=r[s]??0;for(let r of _o)e[r]=t.every(s=>typeof s[r]=="number")?t.reduce((s,o)=>s+o[r],0):void 0;return e.costSavings=e.costAtGridPrice-e.actualCost,e},ge=(t,e)=>{let r=ir(t);return r.size===0?t:t.flatMap(s=>r.has(s.key)?cr(s,e):[s])},lr=(t,e,r=s=>s)=>{let s=ir(t);if(s.size===0)return r(t).map(n=>({device:n,depth:0}));let o=(n,a)=>{if(!s.has(n.key))return[{device:n,depth:a}];let c=r([...s.get(n.key),...cr(n,e)]).flatMap(d=>o(d,a+1)),l=c.filter(d=>!d.device.subtotal).map(d=>d.device);return[{device:{...n,...yo(l),subtotal:!0},depth:a},...c]};return r(t.filter(n=>!n.upstream)).flatMap(n=>o(n,0))};var C=Object.freeze(["#0072b2","#e69f00","#009e73","#cc79a7","#56b4e9","#d55e00","#8c6bb1","#3d9970"]),bo=Object.freeze(["#4b46b3","#8d9b1f","#00a2ab","#b07ad2","#7fa0ee","#a8761b","#b26596","#5b8f3f"]),He=Object.freeze([C,bo]),va=C.length*He.length,Y=Object.freeze({variable:"--secondary-text-color",fallback:"#8a8a8a"}),q=t=>{let e=(t??[]).filter(r=>!r.untracked).map(r=>r.key).sort(vo);return new Map(e.map((r,s)=>{let o=Math.floor(s/C.length)%He.length;return[r,He[o][s%C.length]]}))},vo=(t,e)=>t===e?0:t<e?-1:1;var ye=(t,e,r)=>{let s=t<0?e.lost_share:e.saved_share;return v(s,{percent:U(Math.abs(t),r)})},xo=({costSavings:t,costAtGridPrice:e})=>{if(!(!Number.isFinite(t)||!Number.isFinite(e))&&!(e<=0))return t/e},te=[{at:0,hue:3,light:48,dark:62},{at:.5,hue:35,light:46,dark:68},{at:1,hue:142,light:31,dark:76}],dr={light:85,dark:70},wo=.7,ur=(t,e,r)=>t+(e-t)*r,Eo=.6,So=(t,e)=>{let r=te.findIndex(i=>t<=i.at);if(r<=0)return{hue:te[0].hue,lightness:te[0][e]};let s=te[r-1],o=te[r],n=(t-s.at)/(o.at-s.at),a=r===1?n:n**Eo;return{hue:ur(s.hue,o.hue,a),lightness:ur(s[e],o[e],n)}},hr=.05,M=t=>Math.round(t*10)/10,be=(t,{dark:e=!1}={})=>{let r=e?"dark":"light",s=n=>Math.max(0,n?.costAtGridPrice??0),o=Math.max(0,...(t??[]).map(s));return n=>{let a=xo(n??{});if(a===void 0||o<=0)return;let i=Math.min(1,s(n)/o),c=i*(1+hr)/(i+hr),l=Math.min(1,Math.max(0,a)),{hue:d,lightness:h}=So(l,r),m=dr[r]*c**wo;return{rate:a,text:`hsl(${M(d)}, ${M(m)}%, ${M(h)}%)`,edge:`hsla(${M(d)}, ${M(dr[r])}%, ${M(h)}%, ${M(c)})`}}};var br="hea-device-costs-card",vr=`${br}-editor`,pr={variable:"--error-color",fallback:"#db4437"},ko={variable:"--secondary-text-color",fallback:"#727272"},Ao="earlier-period",Oo=["auto","vertical","horizontal"],To="paid",je="saved",mr="before",Co=30,$o=46,Fo=64,Ro=240,Io=24,No=12,Do=2,Mo=10,Lo=300,Go=120,Po="40vw",Ho={left:8,right:16,top:8,bottom:28,containLabel:!0},fr=1.5,_r=.8,gr=.45,yr=.22,jo=/:(?:paid|saved|before)$/,Bo={gain:{variable:"--success-color",fallback:"#4caf50"},loss:{variable:"--error-color",fallback:"#db4437"}},Wo=(t,e,r,s,o,n,a)=>{let i=document.createElement("div");if(i.append(pe(e),I(s.paid,u(t.actualCost,r))),!a){let d=E(t.costSavings,r);i.append(I(t.costSavings<0?s.lost:s.saved,u(t.costSavings,r),d?o(d):void 0),I(s.would_have_paid,u(t.costAtGridPrice,r)));let h=Uo(n,r,s);h&&i.append(h)}let c=zo(t,r,s,o);c&&i.append(c);let l=Ko(t,r,s);return l&&i.append(l),i},Uo=(t,e,r)=>{if(!t)return;let s=document.createElement("div");return s.style.marginTop="4px",s.style.color=t.text,s.textContent=ye(t.rate,r,e),s},zo=(t,e,r,s)=>{let o=t.before?.actualCost;if(!Number.isFinite(o)||!Number.isFinite(t.actualCost))return;let n=t.actualCost-o,a=B("actualCost",n,e);return I(r.change,v(r.compared,{change:j(n,e),before:u(o,e)}),a?s(a):void 0)},Ko=({costFloor:t,costCeiling:e},r,s)=>{if(![t,e].every(n=>Number.isFinite(n)))return;let o=document.createElement("div");return o.style.marginTop="4px",o.style.opacity="0.75",o.textContent=v(s.range_device,{range:W([t,e],r)}),o},Be=class extends T{static titleKey="title_device_costs";static narrowQuery=N;static getConfigElement(){return document.createElement(vr)}_isEmpty(){return this._ranked().every(e=>!e.costAtGridPrice&&!e.actualCost)}_ranked(){return ge(this._result?.devices??[],this._labels).sort((e,r)=>r.actualCost-e.actualCost||e.name.localeCompare(r.name))}_colourFor(e){if(e.untracked)return this._colour(Y);let r=e.residualOf??e.key;return this._colours().get(r)??C[0]}_colours(){return q(g(this._hass))}_verdicts(){return be(this._ranked(),{dark:de(this)})}_sideways(){let e=this._config?.layout;return e==="horizontal"?!0:e==="vertical"?!1:this._isNarrow()}_comparing(){return this._ranked().some(e=>e.before)}_series(){let e=this._sideways()?this._sidewaysSeries():this._standingSeries();return ne(this._result?.gridOnly?e.filter(({id:r})=>r!==je&&!r.endsWith(`:${je}`)):e)}_sidewaysSeries(){let e=this._ranked(),r=this._colour(pr),s=this._labels,o=n=>this._colourFor(n);return[{id:To,name:s.paid,type:"bar",stack:"cost",data:e.map(n=>({value:n.actualCost,itemStyle:{color:F(o(n),_r)}}))},{id:je,name:s.saved,type:"bar",stack:"cost",data:e.map(n=>{let a=n.costSavings<0?r:o(n);return{value:n.costSavings,itemStyle:{color:F(a,yr),borderColor:a,borderWidth:fr}}})},...this._comparing()?[{id:mr,name:s.compared_series,type:"bar",stack:"earlier",data:e.map(n=>({value:n.before?n.before.actualCost:null,itemStyle:{color:F(o(n),gr)}}))}]:[]]}_standingSeries(){let e=this._colour(pr);return this._ranked().flatMap(r=>{let s=this._colourFor(r),o=r.costSavings<0?e:s,n=r.name;return[{id:`${r.key}:paid`,name:n,type:"bar",stack:r.key,itemStyle:{color:F(s,_r)},data:[r.actualCost]},{id:`${r.key}:saved`,name:n,type:"bar",stack:r.key,itemStyle:{color:F(o,yr),borderColor:o,borderWidth:fr},data:[r.costSavings]},...r.before?[{id:`${r.key}:before`,name:n,type:"bar",stack:`${r.key}:before`,itemStyle:{color:F(s,gr)},data:[r.before.actualCost]}]:[]]})}_tooltipFor({seriesId:e,dataIndex:r},s){let o=this._ranked(),n=this._sideways()?o[r]:o.find(a=>a.key===String(e??"").replace(jo,""));return n?Wo(n,n.name,s,this._labels,a=>this._colour(Bo[a]),this._verdicts()(n),this._result?.gridOnly):void 0}_earlierKey(){if(!this._comparing())return[];let e=this._labels.compared_series,r={color:this._colour(ko)};return this._sideways()?[{id:mr,name:e,itemStyle:r}]:[{id:Ao,secondaryIds:this._ranked().filter(s=>s.before).map(s=>`${s.key}:before`),name:e,itemStyle:r}]}_chartHeight(){if(this._sideways()){let r=this._ranked().length,s=this._comparing()?$o:Co;return`${Math.max(Ro,Fo+r*s)}px`}let e=Lo+this._legendHeight();return`clamp(${e}px, ${Po}, ${e+Go}px)`}_legendHeight(){let e=Math.min(this._ranked().length,Mo)+this._earlierKey().length;return Math.ceil(e/Do)*Io+No}_options(e){return this._sideways()?this._sidewaysOptions(e):this._standingOptions(e)}_sidewaysOptions(e){let r=this._earlierKey();return{xAxis:{type:"value",name:Q(e),axisLabel:{formatter:s=>X(s,e),hideOverlap:!0}},yAxis:{type:"category",data:this._ranked().map(s=>s.name),inverse:!0},grid:Ho,tooltip:{trigger:"item",formatter:s=>this._tooltipFor(s,e)},...r.length?{legend:{show:!0,type:"custom",data:r}}:{}}}_standingOptions(e){return{xAxis:{type:"category",data:[J(this._period,e)]},yAxis:{type:"value",name:Q(e),nameGap:2,nameTextStyle:{align:"left"},axisLabel:{formatter:r=>X(r,e),hideOverlap:!0}},tooltip:{trigger:"item",formatter:r=>this._tooltipFor(r,e)},legend:{show:!0,type:"custom",data:[...this._ranked().map(r=>({id:`${r.key}:paid`,secondaryIds:[`${r.key}:saved`,...r.before?[`${r.key}:before`]:[]],name:r.name,itemStyle:{color:this._colourFor(r)}})),...this._earlierKey()]}}}},We=class extends p{_extraSchema(){return[{name:"layout",selector:{select:{mode:"dropdown",options:Oo}}}]}},Yo=()=>{_(vr,We),f(br,Be,{name:"Home Energy Advisor: Device costs (chart)",description:"What each device cost over the selected period, dearest first."})};Yo();var qo=`${ue}
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
`,Vo=(t,e,r,s)=>(t==="costSavings"?E(r,s):B(e,r,s))??"",Ue=({classes:t=[],styles:e=[]})=>{let r=t.filter(Boolean),s=e.filter(Boolean);return(r.length?` class="${r.join(" ")}"`:"")+(s.length?` style="${s.join("; ")}"`:"")},xr=t=>t?`box-shadow: inset ${Zo} 0 0 ${t.edge}`:"",Zo="4px",L=class extends A{static columns=[];static sorts={};static defaultSort="";static cardStyle=qo;setConfig(e){let{sorts:r}=this.constructor;if(e.sort_by!==void 0&&!(e.sort_by in r))throw new Error(`\`sort_by\` must be one of: ${Object.keys(r).join(", ")}`);super.setConfig(e)}getCardSize(){return 3+Math.ceil((this._result?.devices.length??3)/2)}_columns(){return this.constructor.columns}_body(e){let r=this._columns(),s=this._verdictScale();return`
      <div class="scroll">
        <table>
          <thead><tr>${r.map(o=>this._heading(o,e)).join("")}</tr></thead>
          <tbody>${this._ranked().map(({device:o,depth:n})=>this._row(o,e,s,n)).join("")}</tbody>
          <tfoot>${this._total(e,s)}</tfoot>
        </table>
      </div>`}_verdictScale(){if(this._columns().some(e=>e.carriesVerdict))return be(this._result?.devices??[],{dark:de(this)})}_heading({label:e},r){let s=this._labels;if(typeof e!="function")return`<th>${he(e)}${s[e]}</th>`;let{text:o,unit:n}=e(r,s);return`<th>${o} <span class="unit">${b(n)}</span></th>`}_rank(e){let{sorts:r,defaultSort:s}=this.constructor,{field:o}=r[this._config?.sort_by??s];return[...e].sort((n,a)=>a[o]-n[o]||n.name.localeCompare(a.name))}_ranked(){return lr(this._result?.devices??[],this._labels,e=>this._rank(e))}_row(e,r,s,o){return`<tr${e.subtotal?' class="subtotal"':""}>${this._columns().map(a=>this._cell(a,e,r,s?.(e),o)).join("")}</tr>`}_cell(e,r,s,o,n){let{field:a,derive:i,format:c,reveal:l}=e;if(!c)return`<th scope="row"${Ue({classes:[n?"inside":""],styles:[n?`--depth: ${n}`:"",xr(o)]})}>${b(r.name)}</th>`;let d=i?i(r):r[a],h=this._revealed(c(d,s),l?.(r,s,this._labels));return`<td${this._figureAttributes(e,d,o,s)}>${h}</td>`}_figureAttributes({field:e,tone:r,muted:s,carriesVerdict:o},n,a,i){let c=o?this._verdictOn(a,i):null;return Ue({classes:[Vo(e,r,n,i),s?"muted":""],styles:[c?.style]})+(c?` title="${b(c.title)}"`:"")}_revealed(e,r){return r?`<span class="reveal" tabindex="0" aria-label="${b(r.label)}">${e}<span class="revealed" aria-hidden="true">${b(r.text)}</span></span>`:e}_total(e,r){let s=this._sumOfShown(),o=r?.(s);return`<tr>${this._columns().map(a=>{let{field:i,derive:c,format:l}=a;if(!l)return`<th scope="row"${Ue({styles:[xr(o)]})}>${this._labels.total}</th>`;let d=c?c(s):s[i];return`<td${this._figureAttributes(a,d,o,e)}>${l(d,e)}</td>`}).join("")}</tr>`}_verdictOn(e,r){return e?{style:`color: ${e.text}`,title:ye(e.rate,this._labels,r)}:null}_sumOfShown(){let e=[...new Set(this._columns().flatMap(({field:a,fields:i,derive:c,format:l})=>l?c?i??[]:a?[a]:[]:[]))],r=ge(this._result?.devices??[],this._labels),s=Object.fromEntries(this._columns().flatMap(({fields:a,field:i,readField:c})=>c?(a??[i]).map(l=>[l,c]):[])),o=a=>r.reduce((i,c)=>{for(let l of e){let d=a(c);i[l]+=s[l]?s[l](d,l):d[l]}return i},Object.fromEntries(e.map(i=>[i,0]))),n=o(a=>a);return r.length>0&&r.every(a=>a.before)&&(n.before=o(a=>a.before)),n}},ve=(t,e)=>[{name:"sort_by",selector:{select:{mode:"dropdown",options:Object.entries(t).map(([r,{label:s}])=>({value:r,label:e[s]}))}}}];var Er="hea-devices-card",Sr=`${Er}-editor`,Xo=({actualCost:t,energyUsed:e})=>e>0?t/e:void 0,kr=t=>Object.values(R).every(e=>e in(t.statistics??{})),Ar=t=>({field:t,fields:[t],derive:e=>!e.statistics||ee(e)?e[t]:void 0}),Or={...Ar("costAtGridPrice"),label:"would_have_paid",format:u,muted:!0},Tr={...Ar("costSavings"),label:"saved",format:u},re={fields:["costFloor","costCeiling"],derive:({costFloor:t,costCeiling:e})=>[t,e],label:"range_column",format:W,readField:(t,e)=>Number.isFinite(t[e])?t[e]:t.actualCost},Cr={fields:["actualCost"],derive:({actualCost:t,before:e})=>e&&Number.isFinite(t)&&Number.isFinite(e.actualCost)?t-e.actualCost:void 0,label:"change",format:j,tone:"actualCost"},xe={field:"actualCost",label:"paid",format:u,carriesVerdict:!0,reveal:(t,e)=>{if(!kr(t)||!re.fields.every(s=>Number.isFinite(t[s])))return null;let r=W(re.derive(t),e);return{text:r,label:`${u(t.actualCost,e)} (${r})`}}},$r={field:"forgoneExport",label:"forgone_column",format:u,muted:!0},wr=[{field:"name",label:"device"},{field:"energyUsed",label:"energy",format:$},xe,Cr,re,Or,Tr,$r,{derive:Xo,label:(t,e)=>({text:e.rate,unit:Et(t)}),format:St}],Fr={actual_cost:{field:"actualCost",label:"paid"},cost_at_grid_price:{field:"costAtGridPrice",label:"would_have_paid"},cost_savings:{field:"costSavings",label:"saved"},energy_used:{field:"energyUsed",label:"energy_used"}},ze=class extends L{static titleKey="title_devices";static columns=wr;static sorts=Fr;static defaultSort="actual_cost";static narrowQuery=N;static cardStyle=`${L.cardStyle}
    .disclosure {
      margin-top: var(--hea-space-m);
      color: var(--secondary-text-color);
      font-size: 0.8em;
    }
  `;static getConfigElement(){return document.createElement(Sr)}_columns(){let e=this._rangeAsColumn(),r=new Set;e||r.add(re),this._showsForgone()||r.add($r),this._hasComparison()||r.add(Cr);let s=!!this._result?.gridOnly;return s&&(r.add(Or),r.add(Tr)),wr.filter(o=>!r.has(o)).map(o=>{if(o!==xe)return o;let n=e?{...xe,reveal:void 0}:xe;return s?{...n,carriesVerdict:!1}:n})}_rangeAsColumn(){let e=this._config?.range;return(e==="column"||e!=="rollover"&&!this._isNarrow())&&this._hasEveryBound()}_showsForgone(){return this._hasForgone()&&!this._isNarrow()}_hasComparison(){return(this._result?.devices??[]).some(e=>e.before)}_hasForgone(){return(this._result?.devices??[]).some(e=>(e.forgoneExport??0)>0)}_hasEveryBound(){let e=(this._result?.devices??[]).filter(kr);return e.length>0&&e.every(r=>re.fields.every(s=>Number.isFinite(r[s])))}_body(e){return`${super._body(e)}${this._disclosure(e)}`}_disclosure(e){let r=[this._rangeDisclosure(e),this._forgoneNote()].filter(Boolean);return r.length?`<div class="disclosure">${r.join(" ")}</div>`:""}_forgoneNote(){return this._hasForgone()?this._showsForgone()?this._labels.forgone_note:this._labels.forgone_hidden_note:""}_rangeDisclosure(e){if(this._hasEveryBound())return this._rangeNote();let r=this._result?.wholeHome;if(!r)return"";let s=W([r.costFloor,r.costCeiling],e);return v(this._labels.range_whole_home,{range:s})}_rangeNote(){return this._rangeAsColumn()?this._labels.range_note:this._labels.range_note_rollover}},Ke=class extends p{_extraSchema(){let e=k(this._hass);return[...ve(Fr,e),{name:"range",selector:{select:{mode:"dropdown",options:[{value:"auto",label:e.editor_range_auto},{value:"rollover",label:e.editor_range_rollover},{value:"column",label:e.editor_range_column}]}}}]}},Qo=()=>{_(Sr,Ke),f(Er,ze,{name:"Home Energy Advisor: Devices",description:"Every tracked device over the selected period, ordered by what it cost."})};Qo();var se="household",V=Object.freeze({source:0,household:1,floor:2,area:3,device:4}),Rr=Object.freeze({cost:{field:"actualCost",sources:null},energy:{field:"energyUsed",sources:[{id:"grid",field:"energyFromGrid",variable:"--energy-grid-consumption-color",fallback:"#488fc2"},{id:"generation",field:"energyFromGeneration",variable:"--energy-solar-color",fallback:"#ff9800"},{id:"battery",field:"energyFromBattery",variable:"--energy-battery-out-color",fallback:"#4db6ac"}]}}),Jo=t=>{let e=q(t);return r=>r.untracked?Y.fallback:e.get(r.key)??C[0]},en=({fallback:t})=>t,Mr=(t,e,{metric:r="cost",colour:s=en,deviceColour:o=Jo(t),groupByFloor:n=!0,groupByArea:a=!0}={})=>{let{field:i,sources:c}=Rr[r]??Rr.cost,l=tn(t,i).filter(y=>y.value>0);if(l.length===0)return{nodes:[],links:[]};let d=l.reduce((y,rs)=>y+rs.value,0),h=sn(l,{groupByFloor:n,groupByArea:a}),m=on(l,e,o),w=nn(c,t.filter(y=>y[i]>0),e,s);return{nodes:[...w,{id:se,label:e.household,value:d,index:V.household},...h.nodes,...m.nodes],links:[...w.map(y=>({source:y.id,target:se,value:y.value})),...h.links,...m.links]}},tn=(t,e)=>{let r=new Map(t.map(a=>[a.key,a])),s=new Map,o=[];for(let a of t){let i=rn(a,r);i?s.has(i.key)?s.get(i.key).push(a):s.set(i.key,[a]):o.push(a)}let n=a=>{let i=Math.max(a[e]??0,0),c=(s.get(a.key)??[]).map(n).filter(l=>l.value>0);return{device:a,own:i,inside:c,value:c.reduce((l,d)=>l+d.value,i)}};return o.map(n)},rn=(t,e)=>{let r=e.get(t.upstream);if(!r)return null;let s=new Set;for(let o=r;o;o=e.get(o.upstream)){if(o.key===t.key)return null;if(s.has(o.key))break;s.add(o.key)}return r},sn=(t,{groupByFloor:e,groupByArea:r})=>{let s=new Map,o=new Map,n=[];return t.forEach(({device:a,value:i})=>{let c=e&&a.floorId?Ir(s,a.floorId,a.floorName):null,l=r&&a.areaId?Ir(o,a.areaId,a.areaName):null;c&&(c.value+=i),l&&(l.value+=i,l.floorId??=c?.id??null),n.push({source:an(l,c),target:G(a),value:i})}),{nodes:[...Dr(s,"floor_",V.floor),...Dr(o,"area_",V.area)],links:[...cn(s,o),...n]}},on=(t,e,r)=>{let s=V.device+Lr(t),o=[],n=[],a=(i,c)=>{let{device:l,own:d,inside:h,value:m}=i,w=h.length>0;if(o.push({id:G(l),label:l.name,value:m,index:w?V.device+c:s,color:r(l),...Nr(l)}),!!w&&(h.forEach(y=>{n.push({source:G(l),target:G(y.device),value:y.value}),a(y,c+1)}),d>0)){let y=Pe(l,e);o.push({id:G(y),label:y.name,value:d,index:s,color:r(l),...Nr(l)}),n.push({source:G(l),target:G(y),value:d})}};return t.forEach(i=>a(i,0)),{nodes:o,links:n}},Lr=t=>t.reduce((e,r)=>r.inside.length>0?Math.max(e,1+Lr(r.inside)):e,0),G=t=>`device_${t.key}`,nn=(t,e,r,s)=>(t??[]).map(o=>({id:`source_${o.id}`,label:r[o.id],value:e.reduce((n,a)=>n+(a[o.field]??0),0),index:V.source,color:s(o)})).filter(o=>o.value>0),Ir=(t,e,r)=>(t.has(e)||t.set(e,{id:e,name:r||e,value:0}),t.get(e)),an=(t,e)=>t?`area_${t.id}`:e?`floor_${e.id}`:se,Nr=t=>{let e=t.statistics?.actual_cost;return e?{entityId:e}:{}},Dr=(t,e,r)=>[...t.values()].map(s=>({id:`${e}${s.id}`,label:s.name,value:s.value,index:r})),cn=(t,e)=>[...[...t.values()].map(r=>({source:se,target:`floor_${r.id}`,value:r.value})),...[...e.values()].map(r=>({source:r.floorId?`floor_${r.floorId}`:se,target:`area_${r.id}`,value:r.value}))];var Gr="hea-distribution-card",Pr=`${Gr}-editor`,oe={cost:{titleKey:"title_distribution",emptyKey:"no_cost_in_period",format:u},energy:{titleKey:"title_distribution_energy",emptyKey:"no_energy_in_period",format:$}},ln="400px",dn=88,un=240,hn=["auto","horizontal","vertical"],Ye=Object.freeze({group_by_floor:!0,group_by_area:!0}),qe=class extends T{static titleKey="title_distribution";static chartTag="ha-sankey-chart";static bearingCard={type:"energy-sankey"};static narrowQuery=N;static cardStyle=`
    ha-sankey-chart { display: block; min-height: 240px; }
  `;static getConfigElement(){return document.createElement(Pr)}_isEmpty(){return this._layout().nodes.length===0}_verticalHeight({nodes:e}){let r=new Set(e.map(s=>s.index)).size;return`${Math.max(un,r*dn)}px`}_metric(){return oe[this._config?.metric]?this._config.metric:"cost"}_titleKey(){return oe[this._metric()].titleKey}_emptyKey(){return oe[this._metric()].emptyKey}_layout(){let e=q(g(this._hass));return Mr(this._result?.devices??[],this._labels,{metric:this._metric(),groupByFloor:this._config?.group_by_floor??Ye.group_by_floor,groupByArea:this._config?.group_by_area??Ye.group_by_area,colour:r=>this._colour(r),deviceColour:r=>r.untracked?this._colour(Y):e.get(r.key)??C[0]})}_chartMarkup(){return"<ha-sankey-chart></ha-sankey-chart>"}_draw(e){e.data=this._layout(),e.vertical=this._isVertical(),e.style.height=this._isVertical()?this._verticalHeight(e.data):ln;let r=this._chartLocale(),{format:s}=oe[this._metric()];e.valueFormatter=o=>s(o,r),this.toggleAttribute("data-vertical",e.vertical)}_isVertical(){let e=this._config?.layout;return e==="vertical"?!0:e==="horizontal"?!1:this._isNarrow()}},Ve=class extends p{_extraSchema(){return[{name:"metric",selector:{select:{mode:"dropdown",options:Object.keys(oe)}}},{name:"layout",selector:{select:{mode:"dropdown",options:hn}}},{name:"group_by_floor",selector:{boolean:{}}},{name:"group_by_area",selector:{boolean:{}}}]}setConfig(e){super.setConfig({...Ye,...e})}},pn=()=>{_(Pr,Ve),f(Gr,qe,{name:"Home Energy Advisor: Cost distribution",description:"Where the period's cost went, by floor, room, circuit and device."})};pn();var Hr="hea-filter-card",jr=`${Hr}-editor`,mn=[{kind:"area",label:"filter_rooms",id:"areaId",name:"areaName"},{kind:"floor",label:"filter_floors",id:"floorId",name:"floorName"}],P=({kind:t,id:e})=>`${t}:${e??""}`,fn=t=>{let[e,r]=[t.slice(0,t.indexOf(":")),t.slice(t.indexOf(":")+1)];return{kind:e,id:r===""?null:r}},Ze=class extends HTMLElement{constructor(){super(),this.attachShadow({mode:"open"})}setConfig(e){this._config=e,this._render()}set hass(e){this._hass=e,S(e).then(()=>this._renderIfChanged()),this._renderIfChanged()}getCardSize(){return 1}static getConfigElement(){return document.createElement(jr)}connectedCallback(){this._render(),this._unfilter??=ce(this._config?.collection_key,()=>this._renderIfChanged())}_signature(){return JSON.stringify([this._allDevices().map(e=>[e.key,e.name,e.areaId,e.areaName,e.floorId,e.floorName,e.labels]),P(Z(this._config?.collection_key)),this._labels.filter_rooms])}_renderIfChanged(){this._signature()!==this._drawn&&this._render()}disconnectedCallback(){this._unfilter?.(),this._unfilter=null}get _labels(){return k(this._hass)}_devices(){return g(this._hass).filter(e=>!e.untracked)}_allDevices(){return g(this._hass)}_optionsFor({kind:e,id:r,name:s},o){let n=new Map,a=!1;for(let c of o)c[r]?n.set(c[r],c[s]??c[r]):a=!0;let i=[...n.entries()].map(([c,l])=>({value:P({kind:e,id:c}),text:l})).sort((c,l)=>c.text.localeCompare(l.text));return a&&i.push({value:P({kind:e,id:null}),text:this._labels.filter_unfiled}),i}_labelOptions(e){let r=ht(this._hass);return[...new Set(e.flatMap(o=>o.labels??[]))].map(o=>({value:P({kind:"label",id:o}),text:r[o]??o})).sort((o,n)=>o.text.localeCompare(n.text))}_deviceOptions(){return this._allDevices().map(e=>({value:P({kind:"device",id:e.key}),text:e.name})).sort((e,r)=>e.text.localeCompare(r.text))}_groups(){let e=this._devices(),r=mn.map(o=>({label:this._labels[o.label],options:this._optionsFor(o,e)})),s=this._labelOptions(e);return s.length&&r.push({label:this._labels.filter_labels,options:s}),r.push({label:this._labels.filter_devices,options:this._deviceOptions()}),r.filter(o=>o.options.length>0)}_render(){let e=this._labels,r=this._devices();this._drawn=this._signature();let s=r.length?this._control(e):`<p class="message">${e.no_devices}</p>`;this.shadowRoot.innerHTML=`
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
    `;let o=this.shadowRoot.querySelector("select");o&&(o.value=P(Z(this._config?.collection_key)),o.addEventListener("change",()=>ft(this._config?.collection_key,fn(o.value))))}_control(e){let r=this._groups().map(s=>`<optgroup label="${b(s.label)}">${s.options.map(o=>`<option value="${b(o.value)}">${b(o.text)}</option>`).join("")}</optgroup>`).join("");return`<div class="body">
      <span class="label">${e.title_filter}</span>
      <select>
        <option value="${P({kind:"all",id:null})}">${b(e.filter_everything)}</option>
        ${r}
      </select>
    </div>`}},Xe=class extends p{},_n=()=>{_(jr,Xe),f(Hr,Ze,{name:"Home Energy Advisor: Filter",description:"Narrow every Home Energy Advisor card on the page to a room, a floor, a label or one device."})};_n();var Br="hea-installation-card",Wr=`${Br}-editor`,gn=[{key:"generationSaved",label:"generation_saved"},{key:"batterySaved",label:"battery_saved"},{key:"exportsEarned",label:"exports_earned"}],Qe=class extends A{static titleKey="title_installation";static cardStyle=`
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
  `;static getConfigElement(){return document.createElement(Wr)}getCardSize(){return 4}async _fetch(){if(!this._hass||!this._period)return;let e=++this._request;await S(this._hass);let r=H(this._hass);if(!fe(this._hass,r)){this._state="empty",this._render();return}try{let s={...Xt(r,g(this._hass)),exportsEarned:await this._exportStatistics()},o=await this._hass.callWS({type:"recorder/statistics_during_period",start_time:this._period.start.toISOString(),end_time:this._period.end.toISOString(),statistic_ids:Jt(s),period:O(this._period),types:["change"]});if(e!==this._request)return;this._earned=er(o,s,this._period),this._state="ready"}catch(s){if(e!==this._request)return;this._state="error",console.error(`${this.localName}: could not load statistics`,s)}this._render()}async _exportStatistics(){try{let[e,r]=await Promise.all([this._hass.callWS({type:"energy/get_prefs"}),this._hass.callWS({type:"energy/info"})]);return Qt(e,r)}catch{return[]}}_content(e){return this._state==="empty"?`<p class="message">${this._labels.no_installation}</p>`:super._content(e)}_body(e){let r=this._earned;return`
      <div class="parts">
        ${gn.filter(({key:o})=>r?.[o]!==void 0).map(({key:o,label:n})=>this._line("part",o,this._labels[n],e)).join("")}
        ${this._line("total","total",this._labels.total,e)}
      </div>
      <div class="hint">${this._labels.installation_note}</div>`}_line(e,r,s,o){let n=this._earned?.[r],a=E(n,o);return`
      <div class="${e}">
        <span class="label">${s}</span>
        <span class="value${a?` ${a}`:""}" data-figure="${r}">${u(n,o)}</span>
      </div>`}},Je=class extends p{},yn=()=>{_(Wr,Je),f(Br,Qe,{name:"Home Energy Advisor: What your installation earned",description:"What your generation, battery and exports earned over the selected period, for the whole home."})};yn();var Ur="hea-plans-card",zr=`${Ur}-editor`,bn="home_energy_advisor/compare_plans",vn=[{key:"energy",label:"plans_energy",sign:1},{key:"export",label:"plans_export",figure:"export_credit",sign:-1},{key:"daily",label:"plans_daily",figure:"daily_charges",sign:1}],xn=(t,e)=>t.incomplete||e.incomplete?(t.incomplete?1:0)-(e.incomplete?1:0):t.total-e.total,et=class extends A{static titleKey="title_plans";static cardStyle=`
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
  `;static getConfigElement(){return document.createElement(zr)}getCardSize(){return 5}async _fetch(){if(!this._hass||!this._period)return;let e=++this._request;await S(this._hass);try{let r=await this._hass.callWS({type:bn,start_time:this._period.start.toISOString(),end_time:this._period.end.toISOString()});if(e!==this._request)return;this._compared=r,this._state=r?.plans?.length?"ready":"empty"}catch(r){if(e!==this._request)return;this._state="error",console.error(`${this.localName}: could not compare the plans`,r)}this._render()}_content(e){return this._state==="empty"?`<p class="message">${this._labels.no_plans}</p>`:super._content(e)}_body(e){if(!this._compared?.plans)return"";let r=[...this._compared.plans].sort(xn),s=r.filter(i=>!i.incomplete),o=s.find(i=>i.current),n=s.length>1?s[0]:void 0,a=[this._compared.hours===0?this._labels.plans_no_readings:"",o?"":this._labels.plans_no_current,this._labels.plans_note].filter(Boolean);return`
      <div class="plans">
        ${r.map(i=>this._plan(i,{current:o,cheapest:n},e)).join("")}
      </div>
      ${a.map(wn).join("")}`}_plan(e,{current:r,cheapest:s},o){let n=[e.current?this._labels.plans_your_plan:"",e===s?this._labels.plans_cheapest:""].filter(Boolean).map(c=>`<span class="tag">${c}</span>`).join(""),a=e.incomplete?"":this._total(e,o),i=`
      <div class="head">
        <span class="name">${En(e.name)}${n}</span>
        ${a}
      </div>`;return e.incomplete?`<div class="plan" data-plan="${e.id}">${i}
        <div class="incomplete">${this._labels.plans_incomplete}</div></div>`:`<div class="plan" data-plan="${e.id}">${i}
      <div class="parts">${vn.map(c=>this._part(e,c,o)).join("")}</div>
      ${r&&e!==r?this._difference(e,r,o):""}
    </div>`}_total(e,r){return`<span class="total" data-figure="total:${e.id}">${u(e.total,r)}</span>`}_part(e,{key:r,label:s,figure:o=r,sign:n},a){return`
      <span class="part">${this._labels[s]}
        <span class="value" data-figure="${r}:${e.id}">${u(n*e[o],a)}</span>
      </span>`}_difference(e,r,s){let o=r.total-e.total,n=E(o,s),a=u(Math.abs(o),s),i=this._labels.plans_same;return n==="gain"&&(i=v(this._labels.plans_less,{amount:a})),n==="loss"&&(i=v(this._labels.plans_more,{amount:a})),`<div class="${n?`difference ${n}`:"difference"}" data-figure="difference:${e.id}">${i}</div>`}},wn=t=>`<div class="hint">${t}</div>`,En=t=>String(t).replaceAll(/[&<>"']/g,e=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[e]),tt=class extends p{},Sn=()=>{_(zr,tt),f(Ur,et,{name:"Home Energy Advisor: Compare tariff plans",description:"What each tariff plan you have entered would have cost over the selected period, for the whole home."})};Sn();var qr="hea-self-sufficiency-card",Vr=`${qr}-editor`,Kr=["energyUsed","energyFromGrid","energyFromGeneration","energyFromBattery","energyFromBatterySolar"],kn={maximumFractionDigits:0},Yr=.005,rt=class extends T{static titleKey="title_self_sufficiency";static chartTag="ha-gauge";static bearingCard={type:"energy-self-sufficiency-gauge"};static emptyKey="no_energy_in_period";static cardStyle=`
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
  `;static getConfigElement(){return document.createElement(Vr)}getCardSize(){return 4}_isEmpty(){return this._totals().energyUsed<=0}_totals(){return(this._result?.devices??[]).reduce((e,r)=>{for(let s of Kr)e[s]+=r[s];return e},Object.fromEntries(Kr.map(e=>[e,0])))}_shares(){let e=this._totals(),r=e.energyUsed,s=c=>e[c]/r,o=s("energyFromBatterySolar"),n=s("energyFromGeneration")+o,a=s("energyFromBattery")-o,i=s("energyFromGrid");return{generation:n,storedSolar:o,battery:a,grid:i,unaccounted:Math.max(0,1-n-a-i)}}_body(e){let r=super._body(e);return!this._chartReady||this._isEmpty()?r:`${r}${this._breakdown(e)}`}_chartMarkup(){let e=this._shares().storedSolar>Yr?`<div class="headline">${this._labels.including_stored_solar}</div>`:"";return`<ha-gauge></ha-gauge>
      <div class="headline">${this._labels.from_generation}</div>${e}`}_breakdown(e){let{battery:r,grid:s,unaccounted:o}=this._shares();return`<div class="shares">${[{label:"from_battery_grid",value:r},{label:"from_grid",value:s},{label:"unaccounted",value:o}].filter(({label:a,value:i})=>a!=="unaccounted"||i>Yr).map(({label:a,value:i})=>`
        <div class="share">
          <span class="label">${this._labels[a]}</span>
          <span class="value" data-share="${a}">${U(i,e)}</span>
        </div>`).join("")}</div>
      <div class="note">${this._labels.self_sufficiency_note}</div>`}_draw(e){e.min=0,e.max=100,e.value=this._shares().generation*100,e.label="%",e.formatOptions=kn,e.locale=this._hass?.locale}},st=class extends p{},An=()=>{_(Vr,st),f(qr,rt,{name:"Home Energy Advisor: Self-sufficiency",description:"What share of the selected period's energy came from the household's own generation."})};An();var Zr="hea-sources-card",Xr=`${Zr}-editor`,On=({energyFromGrid:t,energyUsed:e})=>e>0&&t>=0&&t<=e?t/e:void 0,Tn=[{field:"name",label:"device"},{field:"energyUsed",label:"energy",format:$},{field:"energyFromGrid",label:"grid",format:$},{field:"energyFromGeneration",label:"generation",format:$},{field:"energyFromBattery",label:"battery",format:$},{derive:On,label:"from_grid",format:U}],Qr={energy_used:{field:"energyUsed",label:"energy_used"},energy_from_grid:{field:"energyFromGrid",label:"from_grid"},energy_from_generation:{field:"energyFromGeneration",label:"from_generation"},energy_from_battery:{field:"energyFromBattery",label:"from_battery"}},ot=class extends L{static titleKey="title_sources";static columns=Tn;static sorts=Qr;static defaultSort="energy_used";static getConfigElement(){return document.createElement(Xr)}},nt=class extends p{_extraSchema(){return ve(Qr,k(this._hass))}},Cn=()=>{_(Xr,nt),f(Zr,ot,{name:"Home Energy Advisor: Energy sources",description:"Grid, generation and battery behind each device's energy over the period."})};Cn();var es="hea-totals-card",ts=`${es}-editor`,Jr=[{key:"actualCost",label:"paid"},{key:"costAtGridPrice",label:"would_have_paid"},{key:"costSavings",label:"saved"}],at=class extends A{static titleKey="title_totals";static cardStyle=`${ue}
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
  `;static getConfigElement(){return document.createElement(ts)}getCardSize(){return 3}_body(e){let r=this._result?.totals;return`<div class="figures">${(this._result?.gridOnly?Jr.slice(0,1):Jr).map(({key:n,label:a})=>{let i=r?.[n],c=n==="costSavings"?E(i,e):"",l=c?` ${c}`:"";return`
        <div class="figure">
          <span class="label">${he(a)}${this._labels[a]}</span>
          <span class="value${l}" data-figure="${n}">${u(i,e)}</span>
          ${this._comparedTo(n,i,e)}
        </div>`}).join("")}</div>`}_comparedTo(e,r,s){let o=this._result?.totals?.before?.[e];if(!Number.isFinite(o)||!Number.isFinite(r))return"";let n=B(e,r-o,s);return`<span class="${n?`compare ${n}`:"compare"}" data-compare="${e}">${v(this._labels.compared,{change:j(r-o,s),before:u(o,s)})}</span>`}},it=class extends p{},$n=()=>{_(ts,it),f(es,at,{name:"Home Energy Advisor: Totals",description:"What the selected period cost, what it would have cost at grid price, and the difference."})};$n();
