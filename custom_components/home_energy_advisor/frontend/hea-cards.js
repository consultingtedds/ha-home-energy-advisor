var Fs=[4,4,0,0],Rs=[0,0,4,4],Tt=r=>r!==null&&typeof r=="object"&&!Array.isArray(r),Is=r=>{let e=Tt(r)?r.value:r;return Array.isArray(e)?e[1]:e},Me=(r,e)=>{let t=Tt(r)?{...r}:{value:r};return{...t,itemStyle:{...t.itemStyle,...e}}},ye=r=>{let e=Math.max(...r.map(({data:s})=>s.length),0),t=r.map(({data:s})=>[...s]);for(let s of Ns(r))for(let o=0;o<e;o++)Ds(t,o,s);return r.map((s,o)=>({...s,data:t[o]}))},Ns=r=>{let e=new Map;return r.forEach((t,s)=>{let o=t.stack??Symbol(s),n=e.get(o);n?n.push(s):e.set(o,[s])}),[...e.values()]},Ds=(r,e,t)=>{let s=!1,o=!1;for(let n=t.length-1;n>=0;n--){let a=t[n],i=r[a][e];if(i===void 0)continue;let c=Is(i);c?c>0&&!s?(r[a][e]=Me(i,{borderRadius:Fs}),s=!0):c<0&&!o&&(r[a][e]=Me(i,{borderRadius:Rs}),o=!0):r[a][e]=Me(i,{borderWidth:0})}};var Ct="_energy",Ge="energy_";var Ls=(r,e)=>{let t=r||(e?`${Ge}${e}`:"");return t?t.startsWith(Ge)?`_${t}`:`_${Ge}${t}`:Ct},Ms=(r,e)=>typeof r=="string"&&r.startsWith(Ct)&&e!==null&&typeof e=="object"&&typeof e.subscribe=="function"&&"start"in e,Gs=(r=new Date)=>{let e=new Date(r);return e.setDate(e.getDate()-30),e.setHours(0,0,0,0),{start:e,end:r,fallback:!0}},Ps=r=>{let e=r?.connection;if(!e)return{};let t={};for(let s of Object.keys(e)){let o;try{o=e[s]}catch{continue}Ms(s,o)&&(t[s]=o)}return t},Hs=(r,e)=>{let t=Ps(r),s=Ls(e,r?.panelUrl);if(t[s])return t[s];let[o]=Object.values(t);return o??null},js=r=>r?.startCompare&&r?.endCompare?{compare:{start:r.startCompare,end:r.endCompare,mode:r.compareMode}}:{},Ft=(r,e,t)=>{let s=null,o=null,n=0,a=r,i=l=>{if(s)return!0;let d=Hs(l,e);if(!d)return!1;let h=u=>t({start:d.start,end:d.end,fallback:!1,...js(u)});return s=d.subscribe(h),h(),!0},c=()=>{o=setTimeout(()=>{o=null,n+=1,!i(a)&&n<40&&c()},250)};return t(Gs()),i(r)||c(),{retry:l=>(l&&(a=l),i(a)),unsubscribe:()=>{o&&clearTimeout(o),o=null;try{typeof s=="function"&&s()}catch{}s=null}}};var be="sensor.home_energy_advisor_devices",Bs="home_energy_advisor",ve=r=>{if(r?.states?.[be])return be;let e=r?.entities;if(!e)return be;for(let[t,s]of Object.entries(e))if(s?.platform===Bs&&Array.isArray(r?.states?.[t]?.attributes?.devices))return t;return be},v=(r,e=void 0)=>{let t=r?.states?.[e??ve(r)]?.attributes?.devices;return Array.isArray(t)?t.filter(s=>s?.key).map(Nt):[]},G=(r,e=void 0)=>{let t=r?.states?.[e??ve(r)]?.attributes?.whole_home;return t?.key?Nt(t):null},Rt=(r,e=void 0)=>{let t=r?.states?.[e??ve(r)]?.attributes?.settled_until;if(typeof t!="string")return null;let s=new Date(t);return Number.isNaN(s.getTime())?null:s},It=(r,e=void 0)=>{let t=r?.states?.[e??ve(r)]?.attributes?.labels;return t&&typeof t=="object"?t:{}},Nt=r=>({key:r.key,name:r.name||r.key,deviceId:r.device_id??null,untracked:!!r.untracked,statistics:r.statistics??{},areaId:r.area_id??null,areaName:r.area_name??null,floorId:r.floor_id??null,floorName:r.floor_name??null,upstream:r.upstream??null,gross:!!r.gross,labels:Array.isArray(r.labels)?r.labels:[]});var Dt=Object.freeze({kind:"all",id:null}),Ws={area:"areaId",floor:"floorId"},Pe=new Map,He=r=>(Pe.has(r)||Pe.set(r,{filter:Dt,listeners:new Set}),Pe.get(r)),se=r=>He(r).filter,xe=(r,e)=>{let{listeners:t}=He(r);return t.add(e),()=>t.delete(e)},Lt=(r,e)=>{let t=He(r),s={kind:e?.kind??"all",id:e?.id??null};if(!(s.kind===t.filter.kind&&s.id===t.filter.id)){t.filter=s;for(let o of t.listeners)try{o(s)}catch(n){console.warn("home-energy-advisor: a card could not follow the filter",n)}}},Mt=(r,e)=>{let{kind:t,id:s}=e??Dt;if(t==="all")return!0;if(t==="device")return r.key===s;if(r.untracked)return!1;if(t==="label")return(r.labels??[]).includes(s);let o=Ws[t];return o?(r[o]??null)===s:!0};var Gt={day:"numeric",month:"short",year:"numeric"},K=r=>({language:r?.locale?.language||void 0,currency:r?.config?.currency||void 0,timeFormat:r?.locale?.time_format||void 0,timeZone:r?.locale?.time_zone==="server"?r?.config?.time_zone:void 0}),Us=({timeFormat:r,language:e})=>{if(r==="language"||r==="system"||!r){let t=r==="system"?void 0:e;return new Date("January 1, 2023 22:00:00").toLocaleString(t).includes("10")}return r==="12"},oe=(r,e)=>new Intl.DateTimeFormat(e.language,{hour:"numeric",minute:"2-digit",hourCycle:Us(e)?"h12":"h23",timeZone:e.timeZone}).format(r),we=(r,e)=>new Intl.DateTimeFormat(e.language,{...Gt,timeZone:e.timeZone}).format(r),ke=(r,e)=>`${we(r,e)}, ${oe(r,e)}`,zs=(r,e)=>new Intl.DateTimeFormat(e.language,{weekday:"short",month:"short",day:"numeric",timeZone:e.timeZone}).format(r),Ks={hour:3600*1e3},Pt=(r,e,t)=>{let s=Ks[e];if(!s)return zs(r,t);let o=new Date(r.getTime()+s);return`${oe(r,t)} \u2013 ${oe(o,t)}`},m=(r,{language:e,currency:t})=>typeof r!="number"||!Number.isFinite(r)?"-":new Intl.NumberFormat(e,{...Ht(t),signDisplay:"negative"}).format(r),Ht=r=>r?je(r):{minimumFractionDigits:2,maximumFractionDigits:2},je=r=>({style:"currency",currency:r,currencyDisplay:"narrowSymbol"}),jt=(r,{language:e,currency:t}={})=>{let o=10**new Intl.NumberFormat(e,Ht(t)).resolvedOptions().maximumFractionDigits;return Math.round(r*o)/o},Y=(r,{language:e,currency:t})=>{if(typeof r!="number"||!Number.isFinite(r))return"-";let s=t?{...je(t),signDisplay:"exceptZero"}:{minimumFractionDigits:2,maximumFractionDigits:2,signDisplay:"exceptZero"};return new Intl.NumberFormat(e,s).format(r)},Ys=new Set(["actualCost","costAtGridPrice","energyUsed"]),Vs=new Set(["costSavings"]),w=(r,e)=>{if(typeof r!="number"||!Number.isFinite(r))return"";let t=jt(r,e);return t===0?"":t>0?"gain":"loss"},qs=new Set(["actualCost","costAtGridPrice","costSavings"]),V=(r,e,t)=>{if(typeof e!="number"||!Number.isFinite(e))return"";let s=qs.has(r)?jt(e,t):e;return s===0?"":Ys.has(r)?s<0?"gain":"loss":Vs.has(r)?s>0?"gain":"loss":""},q=(r,e)=>{if(!Array.isArray(r))return"-";let[t,s]=r;if(![t,s].every(a=>Number.isFinite(a)))return"-";if(t===s)return m(t,e);let[o,n]=t<=s?[t,s]:[s,t];return`${m(o,e)} - ${m(n,e)}`},y=(r,{language:e})=>typeof r!="number"||!Number.isFinite(r)?"-":`${new Intl.NumberFormat(e,{maximumFractionDigits:1}).format(r)} kWh`,Bt={EUR:{symbol:"c",per:100},USD:{symbol:"\xA2",per:100},GBP:{symbol:"p",per:100}},ne=(r,{language:e})=>typeof r!="number"||!Number.isFinite(r)?"-":new Intl.NumberFormat(e,{minimumFractionDigits:r===0?0:2,maximumFractionDigits:2}).format(r),ae=({language:r,currency:e})=>e?Wt(r,e):"",Wt=(r,e)=>new Intl.NumberFormat(r,je(e)).formatToParts(0).find(t=>t.type==="currency")?.value??"",ie=({language:r,currency:e})=>{if(!e)return"/kWh";let t=Bt[e];return`${t?t.symbol:Wt(r,e)}/kWh`},Z=(r,{language:e,currency:t})=>{if(typeof r!="number"||!Number.isFinite(r))return"-";let s=t?Bt[t]:void 0;return new Intl.NumberFormat(e,{minimumFractionDigits:s?1:0,maximumFractionDigits:s?2:3}).format(s?r*s.per:r)},X=(r,{language:e})=>typeof r!="number"||!Number.isFinite(r)?"-":new Intl.NumberFormat(e,{style:"percent",maximumFractionDigits:0}).format(r),k=r=>String(r).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#39;"),ce=(r,{language:e})=>r?new Intl.DateTimeFormat(e,Gt).formatRange(r.start,r.end):"";var zt="common",Kt="home_energy_advisor",Ut=`component.${Kt}.${zt}.card_`,We=Object.freeze({paid:"Paid",would_have_paid:"Would have paid",saved:"Saved",lost:"Lost",range_column:"Paid (min-max)",range_note:"Paid (min-max) is the widest range these readings allow, not a typical error: a meter that reports every 30-90 minutes leaves the exact moment of use unknown.",range_whole_home:"What you paid could honestly sit between {range} - the widest these readings allow, not a typical error.",range_device:"What you paid could be between {range}.",range_note_rollover:"Hover over or tap a figure in Paid to see the range it could honestly have been. That range is the widest these readings allow, not a typical error: a meter that reports every 30-90 minutes leaves the exact moment of use unknown.",forgone_column:"Could have earned",forgone_note:"Could have earned is what the generation each device used could have earned had you exported it instead, at your export rate at the time. It is money you did not receive, not money you paid, and it is not part of Paid.",forgone_hidden_note:"Could have earned, what the generation each device used could have earned had you exported it instead, is shown on a wider screen.",device_costs_note:"The solid part of each bar is what the device cost. The whole bar is what it would have cost had all its energy come from the grid, at your grid price at the time.",compared:"{change} vs {before}",compared_period:"{period} vs {compared}",saved_share:"{percent} of what you would have paid was saved.",lost_share:"{percent} more was paid than the grid would have cost.",change:"Change",compared_series:"Earlier period",device:"Device",energy:"Energy",rate:"Rate",total:"Total",grid:"Grid",generation:"Generation",battery:"Battery",from_grid:"From the grid",from_generation:"From generation",from_battery:"From the battery",from_battery_grid:"From battery (grid)",of_which_stored_solar:"Of which stored solar",energy_used_came_from:"Where the {energy} of energy used came from",including_stored_solar:"including stored solar",energy_used:"Energy used",unaccounted:"Unaccounted",self_sufficiency_note:"Solar stored in the battery counts as your own. Battery energy charged from the grid does not, and is shown on its own.",household:"Household",generation_saved:"Generation saved",battery_saved:"Battery saved",exports_earned:"Exports earned",installation_note:"For the whole home: your own generation, your battery and your exports, measured against your current tariff. What the battery lost is taken off what it saved.",no_installation:"There is no generation or battery here, so nothing for an installation to have earned.",title_installation:"What your installation earned",title_plans:"Compare tariff plans",tab_summary:"Summary",tab_devices:"Devices",tab_tariffs:"Tariffs",plans_your_plan:"Current plan",plans_cheapest:"Cheapest",plans_energy:"Import cost",plans_export:"Export income",plans_daily:"Daily charges",plans_plan:"Plan",plans_prices:"Prices",plans_you_pay:"What you pay",plans_you_earn:"What you earn",plans_market_price:"Market price",plans_export_rate:"Export",plans_daily_rate:"Daily",plans_per_day:"{amount}/day",plans_total:"Total",plans_without_group:"Buying everything",plans_without:"from the grid",plans_saves:"your installation saves you {amount}",plans_costs_more:"your installation costs you {amount} more",plans_vs_current:"vs current plan",plans_same_short:"The same",plans_flows:"Imported {imported} and exported {exported} in this period.",plans_flows_compared:"Imported {imported} and exported {exported} in the hours compared.",plans_breakdown_hidden:"Import cost, export income and daily charges are shown on a wider screen.",plans_incomplete:"Not every hour has a price, so it cannot be compared. Edit the plan to finish its bands.",plans_note:"For the whole home: each plan priced at the electricity you actually imported and exported, as if your battery had run the same way. Prices are compared as you entered them.",plans_no_readings:"Your grid meters recorded nothing in this period, so there is nothing to compare.",plans_no_current:"Your current plan could not be priced for this period, so no plan is compared with it.",plans_current_daily_missing:"Plans are compared with your current plan once it has its daily charge: Settings > Repairs asks for it.",plans_your_prices:"The prices you pay",plans_your_export_price:"Your export price",plans_daily_missing:"Not given yet",plans_no_price:"{sensors} recorded no statistics in this period, so it cannot be compared. Check it in Developer Tools > Statistics: a price sensor needs the state class measurement for Home Assistant to keep them.",plans_no_price_current:"{sensors} has no statistics for some of this period, so your current plan cannot be priced. To price those hours, choose the plan you were on under Price history from, in your current plan's settings. To keep its statistics from now on, give the sensor the state class measurement.",plans_current_history_from:"Hours your price sensors have no statistics for are priced at {plan}.",plans_export_unpaid:"{amount} of export not paid: capped at each month's energy cost.",plans_export_carried:"{amount} of export carried forward and not yet used.",plans_left_out_meters:"Left out of every plan, daily charges included: {when}. Your grid meters recorded nothing then.",plans_left_out_price:"Left out of every plan, daily charges included: {when}. {sensor} recorded no statistics then. Check it in Developer Tools > Statistics.",plans_left_out_many:"Left out of every plan, daily charges included: {when}. {sources} recorded nothing then. Check any sensor named in Developer Tools > Statistics.",plans_your_grid_meters:"your grid meters",plans_stretch:"{from} to {to}",plans_stretch_kwh:"{from} to {to} ({kwh})",plans_left_out_impossible:"Left out of every plan, daily charges included: {when}. {sensor} recorded more than a home can use in an hour then. Correct it from Settings > Repairs.",plans_open:"Select a plan to see its total line by line, as a bill lists it.",plans_rate:"Rate",plans_used:"Used",plans_amount:"Amount",plans_day:"{days} day",plans_days:"{days} days",plans_unnamed_price:"Price",plans_export_beyond:"Export beyond its allowance",plans_capped:"Not paid under the export cap",plans_average:"average {rate}",plans_average_title:"{average} on average: your cheapest price is {cheapest} and your dearest {dearest}.",plans_average_title_market:"{average} on average: the cheapest hour you imported in was {cheapest}, and the dearest {dearest}.",plans_average_note:"The average is the import cost divided by the kWh imported: worked out from your use, not one of the plan's prices.",plans_market_hourly:"Market prices are applied hour by hour, at each hour's average.",plans_market_five_minutes:"Market prices are applied five minutes at a time.",plans_market_from:"Market prices are applied five minutes at a time from {date}, and hour by hour, at each hour's average, before that.",no_plans:"No tariff plans yet. Add one from the Home Energy Advisor integration, with Add tariff plan.",title_totals:"Cost summary",title_devices:"Cost by device",title_device_costs:"What each device cost",title_cost_over_time:"Cost over time",title_sources:"Where the energy came from",title_self_sufficiency:"Self-sufficiency",title_distribution:"Where the cost went",title_distribution_energy:"Where the energy went",no_devices:"No devices are being tracked yet.",no_devices_in_filter:"No tracked device matches what the page is showing.",title_filter:"Show",filter_everything:"Everything",filter_rooms:"Rooms",filter_floors:"Floors",filter_labels:"Labels",filter_devices:"Devices",filter_unfiled:"Not in one",device_untracked:"Untracked",hourly_shape_estimate:"One device's hourly shape is an estimate: each meter reading is spread across the hours it spanned, so cost may not land in the hour the energy was used.",still_accruing:"The last interval is still being counted, so its bar will grow. Figures are complete about twenty minutes behind the clock, which is how long meters are given to report.",statistics_failed:"Statistics could not be loaded.",loading:"Loading\u2026",no_picker:"Add an Energy date picker card to choose the range.",chart_not_loaded:"Home Assistant's chart component is not loaded. Adding any energy or statistics card to this dashboard will load it.",no_cost_in_period:"No cost recorded in this period.",no_energy_in_period:"No energy recorded in this period.",editor_title:"Title",editor_collection_key:"Energy period (collection key)",editor_devices:"Devices (all, if none are chosen)",editor_sort_by:"Order by",editor_layout:"Layout",editor_metric:"Measure by",editor_group_by_floor:"Group by floor",editor_group_by_area:"Group by area",editor_range:"Show the cost range as",editor_range_auto:"Automatic: a column where there is room",editor_range_rollover:"A rollover on Paid",editor_range_column:"Its own column"}),Be=new Map,Yt=new Map,Vt=r=>r?.locale?.language||r?.language||"en",A=r=>{let e=Vt(r);return Be.has(e)||Be.set(e,Zs(r,e).then(t=>(Yt.set(e,t),t))),Be.get(e)},Zs=async(r,e)=>{try{let{resources:t}=await r.callWS({type:"frontend/get_translations",language:e,category:zt,integration:[Kt]});return Object.freeze({...We,...Xs(t)})}catch(t){return console.warn("home-energy-advisor: falling back to English labels",t),We}},E=r=>Yt.get(Vt(r))??We,Xs=r=>Object.fromEntries(Object.entries(r??{}).filter(([e,t])=>e.startsWith(Ut)&&t).map(([e,t])=>[e.slice(Ut.length),t])),p=(r,e)=>Object.entries(e).reduce((t,[s,o])=>t.replaceAll(`{${s}}`,o),r);var S=Object.freeze({energyUsed:"energy_used",actualCost:"actual_cost",costAtGridPrice:"cost_at_grid_price",energyFromGrid:"energy_from_grid",energyFromGeneration:"energy_from_generation",energyFromBattery:"energy_from_battery",energyFromBatterySolar:"energy_from_battery_solar",forgoneExport:"forgone_export"}),L=Object.freeze({costFloor:"lowest_possible_cost",costCeiling:"highest_possible_cost"}),Ue=()=>Object.fromEntries(Object.keys(S).map(r=>[r,0])),Qt=1440*60*1e3,Jt={hour:3600*1e3,day:Qt},Qs=2,Q=(r,e)=>r?.statistics?.[e],le=r=>S.costAtGridPrice in(r?.statistics??{}),er=(r,e,t,s=!1)=>e==="costAtGridPrice"&&!le(r)?Q(r,S.actualCost):e==="energyFromGrid"&&s?Q(r,S.energyUsed):Q(r,t),Js=r=>[S.energyFromGrid,S.energyFromGeneration,S.energyFromBattery].some(e=>e in(r?.statistics??{})),eo=r=>r.length>0&&!r.some(Js),Ee=(r,e=[])=>{let t=v(r);return eo(t.length?t:e)},to=(r,e)=>{let t=r.flatMap(s=>[...Object.values(S),...Object.values(L)].map(o=>Q(s,o)).filter(Boolean));return!e?.statistics||r.length===0?t:[...t,...Object.values(L).map(s=>Q(e,s)).filter(Boolean)]},tr=(r,e)=>{if(!e)return r;let t=new Map(e.devices.map(s=>[s.key,s]));return{...r,totals:{...r.totals,before:e.totals},devices:r.devices.map(s=>({...s,before:t.get(s.key)})),seriesBefore:ro(e.series,r.period,e.period)}},ro=(r,e,t)=>{if(!r?.length)return;let s=e.start.getTime()-t.start.getTime();return r.map(o=>({...o,start:new Date(o.start.getTime()+s),actualStart:o.start}))},C=({start:r,end:e})=>e-r>Qs*Qt?"day":"hour",qt=(r,e,t)=>{if(e!=="day")return new Date(r.getTime()+t*Jt.hour);let s=new Date(r);return s.setDate(s.getDate()+t),s},rr=(r,e)=>{if(!r.length||!e)return r;let t=C(e),s=new Map(r.map(a=>[a.start.getTime(),a])),o=r[0].start,n=[];for(let a=0;;a--){let i=qt(o,t,a);if(i.getTime()<e.start.getTime())break;n.push(s.get(i.getTime())??Zt(i))}n.reverse();for(let a=1;;a++){let i=qt(o,t,a);if(i.getTime()>=e.end.getTime())break;n.push(s.get(i.getTime())??Zt(i))}return n},Zt=r=>({...Ue(),start:r,costSavings:0,accruing:!1}),Xt=new WeakMap,so=(r,e)=>{let t=r.connection??r,s=Xt.get(t);s||(s=new Map,Xt.set(t,s));let o=JSON.stringify(e),n=s.get(o);if(n)return n;let a=r.callWS(e).finally(()=>s.delete(o));return s.set(o,a),a},ze=async(r,e,t,s,o=null)=>{let n=to(e,s),a=n.length?await so(r,{type:"recorder/statistics_during_period",start_time:t.start.toISOString(),end_time:t.end.toISOString(),statistic_ids:n,period:C(t),types:["change"]}):{},i=Ee(r,e),c=ao(e.map(l=>no(l,a,t,i)));return{period:t,gridOnly:i,devices:c,totals:co(c),wholeHome:sr(s,a,t),series:oo(e,a,t,o,i)}},sr=(r,e,t)=>{if(!r)return;let s={};for(let[o,n]of Object.entries(L)){let a=e?.[Q(r,n)];if(!Array.isArray(a))return;s[o]=nr(a,t)}return s},oo=(r,e,t,s,o)=>{let n=new Map,a=new Set(r.filter(c=>c.gross).map(c=>c.key));for(let c of r.filter(l=>!a.has(l.upstream)))for(let[l,d]of Object.entries(S)){let h=e?.[er(c,l,d,o)];for(let u of or(h,t)){let x=n.get(u.start)??Ue();x[l]+=u.change,n.set(u.start,x)}}let i=Jt[C(t)]??0;return[...n.entries()].sort(([c],[l])=>c-l).map(([c,l])=>({...l,start:new Date(c),costSavings:l.costAtGridPrice-l.actualCost,accruing:s?c+i>s.getTime():!1}))},no=(r,e,t,s)=>{let o=Object.fromEntries(Object.entries(S).map(([n,a])=>[n,nr(e?.[er(r,n,a,s)],t)]));return{...r,...o,...sr(r,e,t),costSavings:o.costAtGridPrice-o.actualCost}},ao=r=>{let e=new Map;for(let t of r)t.upstream&&e.set(t.upstream,[...e.get(t.upstream)??[],t]);return r.map(t=>{if(!t.gross)return t;let s={...t};for(let o of Object.keys(S)){let n=(e.get(t.key)??[]).reduce((a,i)=>a-i[o],t[o]);s[o]=Math.abs(n)<io(o)?0:n}return s.costSavings=s.costAtGridPrice-s.actualCost,s})},io=r=>r.startsWith("energy")?5e-4:.005,or=(r,{start:e,end:t})=>{if(!Array.isArray(r))return[];let s=[];for(let o of r){let n=new Date(o.start).getTime();n<e.getTime()||n>=t.getTime()||typeof o.change=="number"&&s.push({start:n,change:o.change})}return s},nr=(r,e)=>or(r,e).reduce((t,s)=>t+s.change,0),co=r=>({...r.reduce((t,s)=>{for(let o of Object.keys(t))t[o]+=s[o];return t},{...Ue(),costSavings:0}),...lo(r)}),lo=r=>{let e=Object.keys(L);return!r.length||!r.every(t=>e.every(s=>s in t))?{}:Object.fromEntries(e.map(t=>[t,r.reduce((s,o)=>s+o[t],0)]))};var ho=`
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
`,uo=`
  .loss { color: var(--error-color, #db4437); }
  .gain { color: var(--success-color, #4caf50); }
`,I="(max-width: 767px)",O=class extends HTMLElement{static cardStyle="";static narrowQuery="";static titleKey="";_titleKey(){return this.constructor.titleKey}get _labels(){return E(this._hass)}constructor(){super(),this.attachShadow({mode:"open"}),this._state="loading",this._request=0}setConfig(e){if(e.devices!==void 0&&!Array.isArray(e.devices))throw new Error("`devices` must be a list of device keys");this._config=e,this._render()}set hass(e){this._hass=e,this._subscription?this._subscription.retry(e):this._subscribe(),this._refetchIfDevicesChanged()}connectedCallback(){this._render(),this._hass&&!this._subscription&&this._subscribe(),this._watchScreen()}disconnectedCallback(){this._subscription?.unsubscribe(),this._subscription=null,this._unfilter?.(),this._unfilter=null,this._screen?.removeEventListener?.("change",this._onScreenChange),this._screen=null}_watchScreen(){let{narrowQuery:e}=this.constructor;!e||this._screen||(this._screen=globalThis.matchMedia?.(e),this._onScreenChange??=()=>this._render(),this._screen?.addEventListener?.("change",this._onScreenChange))}_isNarrow(){return!!globalThis.matchMedia?.(I)?.matches}_subscribe(){this._subscription=Ft(this._hass,this._config?.collection_key,e=>{this._period=e,this._scheduleFetch()}),this._unfilter=xe(this._config?.collection_key,()=>this._scheduleFetch())}_scheduleFetch(){this._fetchPending||(this._fetchPending=!0,queueMicrotask(()=>{this._fetchPending=!1,this._fetch()}))}_refetchIfDevicesChanged(){let e=this._devices().map(t=>t.key).join(",");e!==this._deviceKeys&&(this._deviceKeys=e,this._period&&this._scheduleFetch())}_devices(){let e=v(this._hass),t=this._config?.devices,s=t?e.filter(n=>t.includes(n.key)):e,o=this._filter();return s.filter(n=>Mt(n,o))}_filter(){return se(this._config?.collection_key)}_isFiltered(){return!!this._config?.devices||this._filter().kind!=="all"}async _fetch(){if(!this._hass||!this._period)return;let e=this._devices(),t=++this._request;if(await A(this._hass),e.length===0){this._state="empty",this._render();return}let s=this._isFiltered()?void 0:G(this._hass);try{let o=Rt(this._hass),[n,a]=await Promise.all([ze(this._hass,e,this._period,s,o),this._period.compare?ze(this._hass,e,this._period.compare,s):void 0]);if(t!==this._request)return;this._result=tr(n,a),this._state="ready"}catch(o){if(t!==this._request)return;this._state="error",console.error(`${this.localName}: could not load statistics`,o)}this._render()}_render(){let e=K(this._hass);this.shadowRoot.innerHTML=`
      <style>${ho}${this.constructor.cardStyle}${uo}</style>
      <ha-card>
        <div class="body" data-state="${this._state}">${this._content(e)}</div>
      </ha-card>
    `;let t=this._config?.title??this._labels[this._titleKey()];t&&this._writeHeader(t,e),this._afterRender()}_writeHeader(e,t){let s=this.shadowRoot.querySelector("ha-card"),o=this._headerChip(t);if(o===void 0){s.setAttribute("header",e);return}s.insertAdjacentHTML("afterbegin",`<div class="card-header" style="display: flex; justify-content: space-between;
         align-items: center; gap: var(--hea-space-s); padding-bottom: 0;">
        <span class="title">${k(e)}</span>
        <span class="chip">${k(o)}</span>
      </div>`)}_headerChip(){}_afterRender(){}_content(e){return this._state==="loading"?`<p class="message" role="status">${this._labels.loading}</p>`:this._state==="empty"?`<p class="message">${this._labels.no_devices}</p>`:this._state==="error"?`<p class="message">${this._labels.statistics_failed}</p>`:`${this._body(e)}${this._caption(e)}`}_caption(e){let t=this._period?.fallback?`<div class="hint">${this._labels.no_picker}</div>`:"";return`<div class="period">${this._periodLabel(e)}</div>${t}`}_periodLabel(e){let t=ce(this._period,e),s=this._period?.compare;return s?p(this._labels.compared_period,{period:t,compared:ce(s,e)}):t}},f=(r,e,{name:t,description:s})=>{customElements.get(r)||customElements.define(r,e),globalThis.customCards=globalThis.customCards??[],globalThis.customCards.some(o=>o.type===r)||globalThis.customCards.push({type:r,name:t,description:s})};var po={title:"editor_title",collection_key:"editor_collection_key",devices:"editor_devices",sort_by:"editor_sort_by",layout:"editor_layout",metric:"editor_metric",group_by_floor:"editor_group_by_floor",group_by_area:"editor_group_by_area",range:"editor_range"},_=class extends HTMLElement{constructor(){super(),this.attachShadow({mode:"open"})}setConfig(e){this._config=e,this._render()}set hass(e){this._hass=e,this._render(),A(e).then(()=>this._render())}_extraSchema(){return[]}_render(){if(!this._config)return;let e=this.shadowRoot.querySelector("ha-form");e||(e=document.createElement("ha-form"),e.computeLabel=t=>E(this._hass)[po[t.name]]??t.name,e.addEventListener("value-changed",t=>this._report(t.detail.value)),this.shadowRoot.append(e)),e.hass=this._hass,e.data=this._config,e.schema=this._schema()}_schema(){return[{name:"title",selector:{text:{}}},{name:"collection_key",selector:{text:{}}},{name:"devices",selector:{select:{multiple:!0,mode:"list",options:v(this._hass).map(e=>({value:e.key,label:e.name}))}}},...this._extraSchema()]}_report(e){this.dispatchEvent(new CustomEvent("config-changed",{detail:{config:mo({...this._config,...e})},bubbles:!0,composed:!0}))}},mo=r=>Object.fromEntries(Object.entries(r).filter(([,e])=>e!==""&&e!==void 0&&e!==null&&!(Array.isArray(e)&&e.length===0))),g=(r,e)=>{customElements.get(r)||customElements.define(r,e)};var F=class extends O{static chartTag="ha-chart-base";static bearingCard={type:"statistics-graph",entities:[]};static emptyKey="no_cost_in_period";static chartHeight="clamp(320px, 40vw, 480px)";static cardStyle=`
    ha-chart-base { display: block; --chart-max-height: none; }
  `;constructor(){super(),this._chartReady=!!customElements.get(this.constructor.chartTag)}getCardSize(){return 6}connectedCallback(){super.connectedCallback(),this._chartReady||this._loadChartComponent()}async _loadChartComponent(){let{chartTag:e,bearingCard:t}=this.constructor;customElements.whenDefined(e).then(()=>{this._chartReady=!0,this._render()});try{await(await globalThis.loadCardHelpers?.())?.createCardElement(t)}catch(s){console.warn(`${e}: could not be loaded`,s)}}_isEmpty(){return(this._result?.series??[]).length===0}_body(){return this._chartReady?this._isEmpty()?`<p class="message">${this._labels[this._emptyKey()]}</p>`:this._chartMarkup():`<p class="message">${this._labels.chart_not_loaded}</p>`}_emptyKey(){return this.constructor.emptyKey}_chartMarkup(){return'<ha-chart-base chart-type="bar"></ha-chart-base>'}_afterRender(){let e=this.shadowRoot.querySelector(this.constructor.chartTag);e&&(e.hass=this._hass,this._draw(e))}_chartHeight(){return this.constructor.chartHeight}_draw(e){e.height=this._chartHeight(),e.data=this._series(),e.options=this._options(this._chartLocale())}_chartLocale(){return K(this._hass)}_colour({variable:e,fallback:t}){return getComputedStyle(this).getPropertyValue(e).trim()||t}};var _o=/^#([\da-f]{3}|[\da-f]{6})$/i,fo=/^rgba?\(([^)]+)\)$/i,Ke=r=>{let e=_o.exec(String(r).trim());if(e){let o=e[1];return(o.length===3?[...o].map(a=>a+a):[0,2,4].map(a=>o.slice(a,a+2))).map(a=>Number.parseInt(a,16))}let t=fo.exec(String(r).trim());if(!t)return;let s=t[1].split(/[\s,/]+/).filter(Boolean).slice(0,3).map(Number);return s.length===3&&s.every(Number.isFinite)?s:void 0},N=(r,e)=>{let t=Ke(String(r).trim());return t?`rgba(${t.join(", ")}, ${e})`:r},go=([r,e,t])=>(.2126*r+.7152*e+.0722*t)/255,J=r=>{let e=Ke(yo(r));return e?go(e)>.5:!1},yo=r=>{let e=[r,r?.ownerDocument?.documentElement].filter(Boolean);for(let t of e){let s=getComputedStyle(t),o=s.getPropertyValue("--primary-text-color").trim()||s.color;if(Ke(o))return o}return""};var ar=Object.freeze({variable:"--primary-color",fallback:"#03a9f4"}),ir=Object.freeze({variable:"--success-color",fallback:"#4caf50"}),bo=Object.freeze({paid:"paid",would_have_paid:"would-have-paid",saved:"saved"}),Se=`
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
`,$e=r=>{let e=typeof r=="string"?bo[r]:void 0;return e?`<span class="swatch ${e}" aria-hidden="true"></span>`:""};var M=(r,e,t,{bold:s=!1}={})=>{let o=document.createElement("div");o.style.display="flex",o.style.justifyContent="space-between",o.style.gap="16px",s&&(o.style.fontWeight="bold");let n=document.createElement("span");n.textContent=r;let a=document.createElement("span");return a.textContent=e,a.style.fontVariantNumeric="tabular-nums",t&&(a.style.color=t),o.append(n,a),o},vo=r=>{let e=document.createElement("span");return e.style.display="inline-block",e.style.width="10px",e.style.height="10px",e.style.borderRadius="10px",e.style.marginInlineEnd="4px",e.style.verticalAlign="middle",e.style.backgroundColor=r,e},cr=(r,e,t,s)=>{let o=M(e,t,s);return o.firstChild.prepend(vo(r)),o},Ae=r=>{let e=document.createElement("div");return e.textContent=r,e.style.fontWeight="bold",e.style.textAlign="center",e.style.marginBottom="4px",e},lr=r=>{let e=document.createElement("div");return e.textContent=r,e.style.marginTop="4px",e.style.maxWidth="260px",e.style.whiteSpace="normal",e.style.opacity="0.7",e};var pr="hea-cost-over-time-card",mr=`${pr}-editor`,xo={hour:3600*1e3,day:1440*60*1e3},wo=50,ko=.5,Eo=(r,e)=>{if(!r.length||!e)return 0;let t=xo[C(e)]??0,s=r.length>=2?r[1].start.getTime()-r[0].start.getTime():void 0;return(s?Math.min(s,t):t)/2},P={paid:{id:"paid",name:"paid",...ar},saved:{id:"saved",name:"saved",...ir}},_r={variable:"--error-color",fallback:"#db4437"},So={gain:{variable:"--success-color",fallback:"#4caf50"},loss:_r},Ye=r=>r.value?.[1]??0,$o=r=>r.value?.[2],Ao=.45,Oe={id:"before",name:"compared_series",variable:"--secondary-text-color",fallback:"#727272"},Ve=class extends F{static titleKey="title_cost_over_time";static getConfigElement(){return document.createElement(mr)}_series(){let e=rr(this._result?.series??[],this._result?.period),t=this._colour(_r),s=this._labels,o=this._result?.seriesBefore,n=Eo(e,this._result?.period),a={...ur(P.paid,this._colour(P.paid),s),data:e.map(c=>dr(c,hr(c,c.actualCost,n)))},i={...ur(P.saved,this._colour(P.saved),s),data:e.map(c=>{let l=hr(c,c.costSavings,n),d=c.costSavings<0?fr(t):void 0;return dr(c,l,d)})};return[...ye(this._result?.gridOnly?[a]:[a,i]),...o?.length?[{id:Oe.id,name:s[Oe.name],type:"line",symbol:"none",lineStyle:{type:"dashed",width:2},itemStyle:{color:this._colour(Oe)},data:o.map(c=>[c.start.getTime()+n,c.costAtGridPrice])}]:[]]}_caption(e){return`${super._caption(e)}${this._stillAccruingNote()}`+this._accrualNote()}_stillAccruingNote(){return(this._result?.series??[]).some(e=>e.accruing)?`<div class="hint">${this._labels.still_accruing}</div>`:""}_accrualNote(){return this._devices().length!==1||!this._period||C(this._period)!=="hour"?"":`<div class="hint">${this._labels.hourly_shape_estimate}</div>`}_tooltipFor(e,t){let s=(Array.isArray(e)?e:[e]).filter(c=>c.componentSubType==="bar"),o=s.filter(c=>Ye(c)!==0);if(!o.length)return;let n=this._bucketAt(s.map($o).find(c=>c!==void 0)),a=document.createElement("div");a.append(Ae(this._spanOf(n,t)));for(let c of o)a.append(this._tooltipRowFor(c,t));let i=s.reduce((c,l)=>c+Ye(l),0);return o.length>1&&a.append(M(this._labels.would_have_paid,m(i,t),void 0,{bold:!0})),n?.accruing&&a.append(lr(this._labels.still_accruing)),a}_tooltipRowFor(e,t){let s=Ye(e),o=e.seriesId===P.saved.id?w(s,t):"",n=o==="loss"?this._labels.lost:e.seriesName;return cr(e.color,n,m(s,t),o?this._colour(So[o]):void 0)}_bucketAt(e){if(e!==void 0)return(this._result?.series??[]).find(t=>t.start.getTime()===e)}_spanOf(e,t){return!e||!this._period?"":Pt(e.start,C(this._period),t)}_headerChip(e){let t=this._result?.totals?.actualCost;return Number.isFinite(t)&&!this._isEmpty()?m(t,e):""}_axisBounds(){if(!this._period)return{};let{start:e,end:t}=this._period,s=new Date(t.getTime()-1);return C(this._period)==="hour"?s.setMinutes(30,0,0):(s.getHours()===0&&s.setHours(s.getHours()-1),s.setHours(0,0,0,0)),{min:e.getTime(),max:s.getTime()}}_options(e){let t=this._labels;return{xAxis:{type:"time",...this._axisBounds()},grid:{top:15,bottom:0,left:1,right:1,containLabel:!0},yAxis:{type:"value",name:ae(e),nameGap:2,nameTextStyle:{align:"left"},boundaryGap:[0,0],splitNumber:5,splitLine:{show:!0},axisLabel:{formatter:s=>ne(s,e),hideOverlap:!0}},tooltip:{trigger:"axis",axisPointer:{type:"shadow"},formatter:s=>this._tooltipFor(s,e)},legend:{show:!0,type:"custom",data:[P.paid,P.saved,...this._result?.seriesBefore?.length?[Oe]:[]].map(s=>({id:s.id,name:t[s.name],itemStyle:{color:this._colour(s)}}))}}}},dr=(r,e,t=void 0)=>r.accruing?{value:e,itemStyle:{...t,opacity:Ao}}:t?{value:e,itemStyle:t}:e,hr=(r,e,t)=>[r.start.getTime()+t,e,r.start.getTime()],ur=({id:r,name:e},t,s)=>({id:r,name:s[e],type:"bar",stack:"cost",barMaxWidth:wo,itemStyle:fr(t)}),fr=r=>({color:N(r,ko),borderColor:r,borderWidth:1}),qe=class extends _{},Oo=()=>{g(mr,qe),f(pr,Ve,{name:"Home Energy Advisor: Cost over time",description:"What the period cost, stacked against what it would have cost at grid price."})};Oo();var de=(r,e)=>{let t=e?.statistics?.cost_savings;return!!(t&&r?.states?.[t])},gr=(r,e)=>({costSavings:r?.statistics?.cost_savings,batterySavings:r?.statistics?.battery_savings,lossesPaid:(e??[]).filter(t=>!t.untracked&&!t.upstream).filter(t=>!le(t)).map(t=>t.statistics?.actual_cost).filter(Boolean)}),yr=(r,e)=>{let t=e?.cost_sensors??{},s=[];for(let o of r?.energy_sources??[]){if(o?.type!=="grid")continue;let n=Array.isArray(o.flow_to)?o.flow_to:[o];for(let a of n){let i=a?.stat_compensation||a?.stat_energy_to&&t[a.stat_energy_to];i&&!s.includes(i)&&s.push(i)}}return s},br=r=>[r.costSavings,r.batterySavings,...r.lossesPaid??[],...r.exportsEarned??[]].filter(Boolean),vr=(r,e,t)=>{let s=u=>To(r?.[u],t),o=s(e.costSavings),n=!!e.batterySavings,a=n?s(e.batterySavings):0,i=(e.lossesPaid??[]).reduce((u,x)=>u+s(x),0),c=e.exportsEarned??[],l=o-a,d=n?a-i:void 0,h=c.length?c.reduce((u,x)=>u+s(x),0):void 0;return{generationSaved:l,batterySaved:d,exportsEarned:h,total:l+(d??0)+(h??0)}},To=(r,{start:e,end:t})=>{if(!Array.isArray(r))return 0;let s=0;for(let o of r){let n=new Date(o.start).getTime();n<e.getTime()||n>=t.getTime()||typeof o.change=="number"&&(s+=o.change)}return s};var et="hea",kr="Home Energy Advisor",Co="mdi:home-lightning-bolt",xr=`ll-strategy-dashboard-${et}`,wr=`ll-strategy-view-${et}`,$=4,Er=[{type:"custom:hea-totals-card"},{type:"custom:hea-devices-card",sort_by:"actual_cost"}],Sr=[{type:"custom:hea-cost-over-time-card"},{type:"custom:hea-sources-card",sort_by:"energy_used"}],Xe=[{type:"custom:hea-device-costs-card"},{type:"custom:hea-distribution-card"},{type:"custom:hea-self-sufficiency-card"}],$r={type:"custom:hea-installation-card"},Fo=new Set(["custom:hea-sources-card","custom:hea-self-sufficiency-card"]),Te=(r,e)=>e?r.filter(t=>!Fo.has(t.type)):r,Ro=r=>de(r,G(r))?[...Xe,$r]:Xe,Io=r=>({...r,grid_options:{columns:"full",rows:"auto"}}),T=(r,e)=>({type:"grid",column_span:e,cards:r.map(Io)}),No=()=>({card:{type:"horizontal-stack",cards:[{type:"energy-date-selection",vertical_opening_direction:"up"},{type:"custom:hea-filter-card"}]},max_width:1600}),Ar=r=>({type:"sections",max_columns:$,sections:[{type:"grid",cards:[{type:"markdown",content:E(r).no_devices}]}]}),Or={type:"custom:hea-plans-card"},Do=async r=>{try{let e=await r.callWS({type:"home_energy_advisor/list_plans"});return Array.isArray(e?.plans)&&e.plans.some(t=>!t.current)}catch{return!1}},Tr=r=>({type:"sections",max_columns:$,sections:r.filter(e=>e.cards.length>0),footer:No()}),Lo=(r,e)=>{if(v(r).length===0)return Ar(r);let t=Ee(r);return Tr([T(Er,$),T(Te(Sr,t),$/2),T(Te(Ro(r),t),$/2),...e?[T([Or],$)]:[]])},[Mo,Go]=Er,[Po,Ho]=Sr,[jo,Bo,Wo]=Xe,Ze=(r,{path:e,titleKey:t,icon:s},o)=>({...Tr(o),path:e,title:E(r)[t],icon:s}),Uo=(r,e)=>{if(v(r).length===0)return[Ar(r)];let t=Ee(r),s=de(r,G(r))?[$r]:[],o=[Ze(r,{path:"summary",titleKey:"tab_summary",icon:"mdi:view-dashboard"},[T([Mo],$),T([Po,...s],$/2),T(Te([Bo,Wo],t),$/2)]),Ze(r,{path:"devices",titleKey:"tab_devices",icon:"mdi:format-list-bulleted"},[T([Go],$),T([jo],$/2),T(Te([Ho],t),$/2)])];return e&&o.push(Ze(r,{path:"tariffs",titleKey:"tab_tariffs",icon:"mdi:cash-multiple"},[T([Or],$)])),o},Cr=async r=>{let[,e]=await Promise.all([A(r),Do(r)]);return e},Qe=class extends HTMLElement{static async generate(e,t){return{views:Uo(t,await Cr(t))}}static noEditor=!0;static getCreateSuggestions(){return{title:kr,icon:Co}}},Je=class extends HTMLElement{static async generate(e,t){return Lo(t,await Cr(t))}},zo=r=>{globalThis.customStrategies=globalThis.customStrategies??[],globalThis.customStrategies.some(e=>e.type===r.type)||globalThis.customStrategies.push(r)},Ko=()=>{customElements.get(xr)||customElements.define(xr,Qe),customElements.get(wr)||customElements.define(wr,Je),zo({type:et,strategyType:"dashboard",name:kr,description:"What each device cost to run, and what solar and the battery saved."})};Ko();var tt=Object.keys(S),Yo=Object.keys(L),Fr=r=>{let e=new Map;for(let t of r){if(!t.upstream)continue;let s=e.get(t.upstream);s?s.push(t):e.set(t.upstream,[t])}return e},rt=(r,e)=>({...r,key:`${r.key}${Vo}`,name:`${r.name} ${e.device_untracked}`,upstream:r.key,untracked:!1,gross:!1,residualOf:r.key}),Vo="__untracked",Rr=(r,e)=>r.gross&&tt.every(t=>!r[t])?[]:[rt(r,e)],qo=r=>{let e=Object.fromEntries(tt.map(t=>[t,0]));for(let t of r)for(let s of tt)e[s]+=t[s]??0;for(let t of Yo)e[t]=r.every(s=>typeof s[t]=="number")?r.reduce((s,o)=>s+o[t],0):void 0;return e.costSavings=e.costAtGridPrice-e.actualCost,e},Ce=(r,e)=>{let t=Fr(r);return t.size===0?r:r.flatMap(s=>t.has(s.key)?Rr(s,e):[s])},Ir=(r,e,t=s=>s)=>{let s=Fr(r);if(s.size===0)return t(r).map(n=>({device:n,depth:0}));let o=(n,a)=>{if(!s.has(n.key))return[{device:n,depth:a}];let c=t([...s.get(n.key),...Rr(n,e)]).flatMap(d=>o(d,a+1)),l=c.filter(d=>!d.device.subtotal).map(d=>d.device);return[{device:{...n,...qo(l),subtotal:!0},depth:a},...c]};return t(r.filter(n=>!n.upstream)).flatMap(n=>o(n,0))};var R=Object.freeze(["#0072b2","#e69f00","#009e73","#cc79a7","#56b4e9","#d55e00","#8c6bb1","#3d9970"]),Zo=Object.freeze(["#4b46b3","#8d9b1f","#00a2ab","#b07ad2","#7fa0ee","#a8761b","#b26596","#5b8f3f"]),st=Object.freeze([R,Zo]),Xa=R.length*st.length,ee=Object.freeze({variable:"--secondary-text-color",fallback:"#8a8a8a"}),te=r=>{let e=(r??[]).filter(t=>!t.untracked).map(t=>t.key).sort(Xo);return new Map(e.map((t,s)=>{let o=Math.floor(s/R.length)%st.length;return[t,st[o][s%R.length]]}))},Xo=(r,e)=>r===e?0:r<e?-1:1;var Fe=(r,e,t)=>{let s=r<0?e.lost_share:e.saved_share;return p(s,{percent:X(Math.abs(r),t)})},Qo=({costSavings:r,costAtGridPrice:e})=>{if(!(!Number.isFinite(r)||!Number.isFinite(e))&&!(e<=0))return r/e},he=[{at:0,hue:3,light:48,dark:62},{at:.5,hue:35,light:46,dark:68},{at:1,hue:142,light:31,dark:76}],Nr={light:85,dark:70},Jo=.7,Dr=(r,e,t)=>r+(e-r)*t,en=.6,tn=(r,e)=>{let t=he.findIndex(i=>r<=i.at);if(t<=0)return{hue:he[0].hue,lightness:he[0][e]};let s=he[t-1],o=he[t],n=(r-s.at)/(o.at-s.at),a=t===1?n:n**en;return{hue:Dr(s.hue,o.hue,a),lightness:Dr(s[e],o[e],n)}},Lr=.05,H=r=>Math.round(r*10)/10,ot=(r,{dark:e=!1,weight:t=1}={})=>{let s=e?"dark":"light",{hue:o,lightness:n}=tn(Math.min(1,Math.max(0,r)),s),a=Nr[s]*t**Jo;return{text:`hsl(${H(o)}, ${H(a)}%, ${H(n)}%)`,edge:`hsla(${H(o)}, ${H(Nr[s])}%, ${H(n)}%, ${H(t)})`}},Re=(r,{dark:e=!1}={})=>{let t=o=>Math.max(0,o?.costAtGridPrice??0),s=Math.max(0,...(r??[]).map(t));return o=>{let n=Qo(o??{});if(n===void 0||s<=0)return;let a=Math.min(1,t(o)/s),i=a*(1+Lr)/(a+Lr);return{rate:n,...ot(n,{dark:e,weight:i})}}};var Wr="hea-device-costs-card",Ur=`${Wr}-editor`,Mr={variable:"--error-color",fallback:"#db4437"},rn={variable:"--secondary-text-color",fallback:"#727272"},sn="earlier-period",on=["auto","vertical","horizontal"],nn="paid",nt="saved",Gr="before",an=30,cn=46,ln=64,dn=240,hn=24,un=12,pn=2,mn=10,_n=300,fn=120,gn="40vw",yn={left:8,right:16,top:8,bottom:28,containLabel:!0},Pr=1.5,Hr=.8,jr=.45,Br=.22,bn=/:(?:paid|saved|before)$/,vn={gain:{variable:"--success-color",fallback:"#4caf50"},loss:{variable:"--error-color",fallback:"#db4437"}},xn=(r,e,t,s,o,n,a)=>{let i=document.createElement("div");if(i.append(Ae(e),M(s.paid,m(r.actualCost,t))),!a){let d=w(r.costSavings,t);i.append(M(r.costSavings<0?s.lost:s.saved,m(r.costSavings,t),d?o(d):void 0),M(s.would_have_paid,m(r.costAtGridPrice,t)));let h=wn(n,t,s);h&&i.append(h)}let c=kn(r,t,s,o);c&&i.append(c);let l=En(r,t,s);return l&&i.append(l),i},wn=(r,e,t)=>{if(!r)return;let s=document.createElement("div");return s.style.marginTop="4px",s.style.color=r.text,s.textContent=Fe(r.rate,t,e),s},kn=(r,e,t,s)=>{let o=r.before?.actualCost;if(!Number.isFinite(o)||!Number.isFinite(r.actualCost))return;let n=r.actualCost-o,a=V("actualCost",n,e);return M(t.change,p(t.compared,{change:Y(n,e),before:m(o,e)}),a?s(a):void 0)},En=({costFloor:r,costCeiling:e},t,s)=>{if(![r,e].every(n=>Number.isFinite(n)))return;let o=document.createElement("div");return o.style.marginTop="4px",o.style.opacity="0.75",o.textContent=p(s.range_device,{range:q([r,e],t)}),o},at=class extends F{static titleKey="title_device_costs";static narrowQuery=I;static getConfigElement(){return document.createElement(Ur)}_isEmpty(){return this._ranked().every(e=>!e.costAtGridPrice&&!e.actualCost)}_caption(e){let t=super._caption(e);return this._isEmpty()?t:`${t}<div class="hint">${this._labels.device_costs_note}</div>`}_ranked(){return Ce(this._result?.devices??[],this._labels).sort((e,t)=>t.actualCost-e.actualCost||e.name.localeCompare(t.name))}_colourFor(e){if(e.untracked)return this._colour(ee);let t=e.residualOf??e.key;return this._colours().get(t)??R[0]}_colours(){return te(v(this._hass))}_verdicts(){return Re(this._ranked(),{dark:J(this)})}_sideways(){let e=this._config?.layout;return e==="horizontal"?!0:e==="vertical"?!1:this._isNarrow()}_comparing(){return this._ranked().some(e=>e.before)}_series(){let e=this._sideways()?this._sidewaysSeries():this._standingSeries();return ye(this._result?.gridOnly?e.filter(({id:t})=>t!==nt&&!t.endsWith(`:${nt}`)):e)}_sidewaysSeries(){let e=this._ranked(),t=this._colour(Mr),s=this._labels,o=n=>this._colourFor(n);return[{id:nn,name:s.paid,type:"bar",stack:"cost",data:e.map(n=>({value:n.actualCost,itemStyle:{color:N(o(n),Hr)}}))},{id:nt,name:s.saved,type:"bar",stack:"cost",data:e.map(n=>{let a=n.costSavings<0?t:o(n);return{value:n.costSavings,itemStyle:{color:N(a,Br),borderColor:a,borderWidth:Pr}}})},...this._comparing()?[{id:Gr,name:s.compared_series,type:"bar",stack:"earlier",data:e.map(n=>({value:n.before?n.before.actualCost:null,itemStyle:{color:N(o(n),jr)}}))}]:[]]}_standingSeries(){let e=this._colour(Mr);return this._ranked().flatMap(t=>{let s=this._colourFor(t),o=t.costSavings<0?e:s,n=t.name;return[{id:`${t.key}:paid`,name:n,type:"bar",stack:t.key,itemStyle:{color:N(s,Hr)},data:[t.actualCost]},{id:`${t.key}:saved`,name:n,type:"bar",stack:t.key,itemStyle:{color:N(o,Br),borderColor:o,borderWidth:Pr},data:[t.costSavings]},...t.before?[{id:`${t.key}:before`,name:n,type:"bar",stack:`${t.key}:before`,itemStyle:{color:N(s,jr)},data:[t.before.actualCost]}]:[]]})}_tooltipFor({seriesId:e,dataIndex:t},s){let o=this._ranked(),n=this._sideways()?o[t]:o.find(a=>a.key===String(e??"").replace(bn,""));return n?xn(n,n.name,s,this._labels,a=>this._colour(vn[a]),this._verdicts()(n),this._result?.gridOnly):void 0}_earlierKey(){if(!this._comparing())return[];let e=this._labels.compared_series,t={color:this._colour(rn)};return this._sideways()?[{id:Gr,name:e,itemStyle:t}]:[{id:sn,secondaryIds:this._ranked().filter(s=>s.before).map(s=>`${s.key}:before`),name:e,itemStyle:t}]}_chartHeight(){if(this._sideways()){let t=this._ranked().length,s=this._comparing()?cn:an;return`${Math.max(dn,ln+t*s)}px`}let e=_n+this._legendHeight();return`clamp(${e}px, ${gn}, ${e+fn}px)`}_legendHeight(){let e=Math.min(this._ranked().length,mn)+this._earlierKey().length;return Math.ceil(e/pn)*hn+un}_options(e){return this._sideways()?this._sidewaysOptions(e):this._standingOptions(e)}_sidewaysOptions(e){let t=this._earlierKey();return{xAxis:{type:"value",name:ae(e),axisLabel:{formatter:s=>ne(s,e),hideOverlap:!0}},yAxis:{type:"category",data:this._ranked().map(s=>s.name),inverse:!0},grid:yn,tooltip:{trigger:"item",formatter:s=>this._tooltipFor(s,e)},...t.length?{legend:{show:!0,type:"custom",data:t}}:{}}}_standingOptions(e){return{xAxis:{type:"category",data:[ce(this._period,e)]},yAxis:{type:"value",name:ae(e),nameGap:2,nameTextStyle:{align:"left"},axisLabel:{formatter:t=>ne(t,e),hideOverlap:!0}},tooltip:{trigger:"item",formatter:t=>this._tooltipFor(t,e)},legend:{show:!0,type:"custom",data:[...this._ranked().map(t=>({id:`${t.key}:paid`,secondaryIds:[`${t.key}:saved`,...t.before?[`${t.key}:before`]:[]],name:t.name,itemStyle:{color:this._colourFor(t)}})),...this._earlierKey()]}}}},it=class extends _{_extraSchema(){return[{name:"layout",selector:{select:{mode:"dropdown",options:on}}}]}},Sn=()=>{g(Ur,it),f(Wr,at,{name:"Home Energy Advisor: Device costs (chart)",description:"What each device cost over the selected period, dearest first."})};Sn();var lt=`${Se}
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
`,$n=(r,e,t,s)=>(r==="costSavings"?w(t,s):V(e,t,s))??"",ct=({classes:r=[],styles:e=[]})=>{let t=r.filter(Boolean),s=e.filter(Boolean);return(t.length?` class="${t.join(" ")}"`:"")+(s.length?` style="${s.join("; ")}"`:"")},zr=r=>r?`box-shadow: inset ${An} 0 0 ${r.edge}`:"",An="4px",j=class extends O{static columns=[];static sorts={};static defaultSort="";static cardStyle=lt;setConfig(e){let{sorts:t}=this.constructor;if(e.sort_by!==void 0&&!(e.sort_by in t))throw new Error(`\`sort_by\` must be one of: ${Object.keys(t).join(", ")}`);super.setConfig(e)}getCardSize(){return 3+Math.ceil((this._result?.devices.length??3)/2)}_columns(){return this.constructor.columns}_body(e){let t=this._columns(),s=this._verdictScale();return`
      <div class="scroll">
        <table>
          <thead><tr>${t.map(o=>this._heading(o,e)).join("")}</tr></thead>
          <tbody>${this._ranked().map(({device:o,depth:n})=>this._row(o,e,s,n)).join("")}</tbody>
          <tfoot>${this._total(e,s)}</tfoot>
        </table>
      </div>`}_verdictScale(){if(this._columns().some(e=>e.carriesVerdict))return Re(this._result?.devices??[],{dark:J(this)})}_heading({label:e},t){let s=this._labels;if(typeof e!="function")return`<th>${$e(e)}${s[e]}</th>`;let{text:o,unit:n}=e(t,s);return`<th>${o} <span class="unit">${k(n)}</span></th>`}_rank(e){let{sorts:t,defaultSort:s}=this.constructor,{field:o}=t[this._config?.sort_by??s];return[...e].sort((n,a)=>a[o]-n[o]||n.name.localeCompare(a.name))}_ranked(){return Ir(this._result?.devices??[],this._labels,e=>this._rank(e))}_row(e,t,s,o){return`<tr${e.subtotal?' class="subtotal"':""}>${this._columns().map(a=>this._cell(a,e,t,s?.(e),o)).join("")}</tr>`}_cell(e,t,s,o,n){let{field:a,derive:i,format:c,reveal:l}=e;if(!c)return`<th scope="row"${ct({classes:[n?"inside":""],styles:[n?`--depth: ${n}`:"",zr(o)]})}>${k(t.name)}</th>`;let d=i?i(t):t[a],h=this._revealed(c(d,s),l?.(t,s,this._labels));return`<td${this._figureAttributes(e,d,o,s)}>${h}</td>`}_figureAttributes({field:e,tone:t,muted:s,carriesVerdict:o},n,a,i){let c=o?this._verdictOn(a,i):null;return ct({classes:[$n(e,t,n,i),s?"muted":""],styles:[c?.style]})+(c?` title="${k(c.title)}"`:"")}_revealed(e,t){return t?`<span class="reveal" tabindex="0" aria-label="${k(t.label)}">${e}<span class="revealed" aria-hidden="true">${k(t.text)}</span></span>`:e}_total(e,t){let s=this._sumOfShown(),o=t?.(s);return`<tr>${this._columns().map(a=>{let{field:i,derive:c,format:l}=a;if(!l)return`<th scope="row"${ct({styles:[zr(o)]})}>${this._labels.total}</th>`;let d=c?c(s):s[i];return`<td${this._figureAttributes(a,d,o,e)}>${l(d,e)}</td>`}).join("")}</tr>`}_verdictOn(e,t){return e?{style:`color: ${e.text}`,title:Fe(e.rate,this._labels,t)}:null}_sumOfShown(){let e=[...new Set(this._columns().flatMap(({field:a,fields:i,derive:c,format:l})=>l?c?i??[]:a?[a]:[]:[]))],t=Ce(this._result?.devices??[],this._labels),s=Object.fromEntries(this._columns().flatMap(({fields:a,field:i,readField:c})=>c?(a??[i]).map(l=>[l,c]):[])),o=a=>t.reduce((i,c)=>{for(let l of e){let d=a(c);i[l]+=s[l]?s[l](d,l):d[l]}return i},Object.fromEntries(e.map(i=>[i,0]))),n=o(a=>a);return t.length>0&&t.every(a=>a.before)&&(n.before=o(a=>a.before)),n}},Ie=(r,e)=>[{name:"sort_by",selector:{select:{mode:"dropdown",options:Object.entries(r).map(([t,{label:s}])=>({value:t,label:e[s]}))}}}];var Yr="hea-devices-card",Vr=`${Yr}-editor`,On=({actualCost:r,energyUsed:e})=>e>0?r/e:void 0,qr=r=>Object.values(L).every(e=>e in(r.statistics??{})),Zr=r=>({field:r,fields:[r],derive:e=>!e.statistics||le(e)?e[r]:void 0}),Xr={...Zr("costAtGridPrice"),label:"would_have_paid",format:m,muted:!0},Qr={...Zr("costSavings"),label:"saved",format:m},ue={fields:["costFloor","costCeiling"],derive:({costFloor:r,costCeiling:e})=>[r,e],label:"range_column",format:q,readField:(r,e)=>Number.isFinite(r[e])?r[e]:r.actualCost},Jr={fields:["actualCost"],derive:({actualCost:r,before:e})=>e&&Number.isFinite(r)&&Number.isFinite(e.actualCost)?r-e.actualCost:void 0,label:"change",format:Y,tone:"actualCost"},Ne={field:"actualCost",label:"paid",format:m,carriesVerdict:!0,reveal:(r,e)=>{if(!qr(r)||!ue.fields.every(s=>Number.isFinite(r[s])))return null;let t=q(ue.derive(r),e);return{text:t,label:`${m(r.actualCost,e)} (${t})`}}},es={field:"forgoneExport",label:"forgone_column",format:m,muted:!0},Kr=[{field:"name",label:"device"},{field:"energyUsed",label:"energy",format:y},Ne,Jr,ue,Xr,Qr,es,{derive:On,label:(r,e)=>({text:e.rate,unit:ie(r)}),format:Z}],ts={actual_cost:{field:"actualCost",label:"paid"},cost_at_grid_price:{field:"costAtGridPrice",label:"would_have_paid"},cost_savings:{field:"costSavings",label:"saved"},energy_used:{field:"energyUsed",label:"energy_used"}},dt=class extends j{static titleKey="title_devices";static columns=Kr;static sorts=ts;static defaultSort="actual_cost";static narrowQuery=I;static cardStyle=`${j.cardStyle}
    .disclosure {
      margin-top: var(--hea-space-m);
      color: var(--secondary-text-color);
      font-size: 0.8em;
    }
  `;static getConfigElement(){return document.createElement(Vr)}_columns(){let e=this._rangeAsColumn(),t=new Set;e||t.add(ue),this._showsForgone()||t.add(es),this._hasComparison()||t.add(Jr);let s=!!this._result?.gridOnly;return s&&(t.add(Xr),t.add(Qr)),Kr.filter(o=>!t.has(o)).map(o=>{if(o!==Ne)return o;let n=e?{...Ne,reveal:void 0}:Ne;return s?{...n,carriesVerdict:!1}:n})}_rangeAsColumn(){let e=this._config?.range;return(e==="column"||e!=="rollover"&&!this._isNarrow())&&this._hasEveryBound()}_showsForgone(){return this._hasForgone()&&!this._isNarrow()}_hasComparison(){return(this._result?.devices??[]).some(e=>e.before)}_hasForgone(){return(this._result?.devices??[]).some(e=>(e.forgoneExport??0)>0)}_hasEveryBound(){let e=(this._result?.devices??[]).filter(qr);return e.length>0&&e.every(t=>ue.fields.every(s=>Number.isFinite(t[s])))}_body(e){return`${super._body(e)}${this._disclosure(e)}`}_disclosure(e){let t=[this._rangeDisclosure(e),this._forgoneNote()].filter(Boolean);return t.length?`<div class="disclosure">${t.join(" ")}</div>`:""}_forgoneNote(){return this._hasForgone()?this._showsForgone()?this._labels.forgone_note:this._labels.forgone_hidden_note:""}_rangeDisclosure(e){if(this._hasEveryBound())return this._rangeNote();let t=this._result?.wholeHome;if(!t)return"";let s=q([t.costFloor,t.costCeiling],e);return p(this._labels.range_whole_home,{range:s})}_rangeNote(){return this._rangeAsColumn()?this._labels.range_note:this._labels.range_note_rollover}},ht=class extends _{_extraSchema(){let e=E(this._hass);return[...Ie(ts,e),{name:"range",selector:{select:{mode:"dropdown",options:[{value:"auto",label:e.editor_range_auto},{value:"rollover",label:e.editor_range_rollover},{value:"column",label:e.editor_range_column}]}}}]}},Tn=()=>{g(Vr,ht),f(Yr,dt,{name:"Home Energy Advisor: Devices",description:"Every tracked device over the selected period, ordered by what it cost."})};Tn();var pe="household",re=Object.freeze({source:0,household:1,floor:2,area:3,device:4}),rs=Object.freeze({cost:{field:"actualCost",sources:null},energy:{field:"energyUsed",sources:[{id:"grid",field:"energyFromGrid",variable:"--energy-grid-consumption-color",fallback:"#488fc2"},{id:"generation",field:"energyFromGeneration",variable:"--energy-solar-color",fallback:"#ff9800"},{id:"battery",field:"energyFromBattery",variable:"--energy-battery-out-color",fallback:"#4db6ac"}]}}),Cn=r=>{let e=te(r);return t=>t.untracked?ee.fallback:e.get(t.key)??R[0]},Fn=({fallback:r})=>r,as=(r,e,{metric:t="cost",colour:s=Fn,deviceColour:o=Cn(r),groupByFloor:n=!0,groupByArea:a=!0}={})=>{let{field:i,sources:c}=rs[t]??rs.cost,l=Rn(r,i).filter(b=>b.value>0);if(l.length===0)return{nodes:[],links:[]};let d=l.reduce((b,fe)=>b+fe.value,0),h=Nn(l,{groupByFloor:n,groupByArea:a}),u=Dn(l,e,o),x=Ln(c,r.filter(b=>b[i]>0),e,s);return{nodes:[...x,{id:pe,label:e.household,value:d,index:re.household},...h.nodes,...u.nodes],links:[...x.map(b=>({source:b.id,target:pe,value:b.value})),...h.links,...u.links]}},Rn=(r,e)=>{let t=new Map(r.map(a=>[a.key,a])),s=new Map,o=[];for(let a of r){let i=In(a,t);i?s.has(i.key)?s.get(i.key).push(a):s.set(i.key,[a]):o.push(a)}let n=a=>{let i=Math.max(a[e]??0,0),c=(s.get(a.key)??[]).map(n).filter(l=>l.value>0);return{device:a,own:i,inside:c,value:c.reduce((l,d)=>l+d.value,i)}};return o.map(n)},In=(r,e)=>{let t=e.get(r.upstream);if(!t)return null;let s=new Set;for(let o=t;o;o=e.get(o.upstream)){if(o.key===r.key)return null;if(s.has(o.key))break;s.add(o.key)}return t},Nn=(r,{groupByFloor:e,groupByArea:t})=>{let s=new Map,o=new Map,n=[];return r.forEach(({device:a,value:i})=>{let c=e&&a.floorId?ss(s,a.floorId,a.floorName):null,l=t&&a.areaId?ss(o,a.areaId,a.areaName):null;c&&(c.value+=i),l&&(l.value+=i,l.floorId??=c?.id??null),n.push({source:Mn(l,c),target:B(a),value:i})}),{nodes:[...ns(s,"floor_",re.floor),...ns(o,"area_",re.area)],links:[...Gn(s,o),...n]}},Dn=(r,e,t)=>{let s=re.device+is(r),o=[],n=[],a=(i,c)=>{let{device:l,own:d,inside:h,value:u}=i,x=h.length>0;if(o.push({id:B(l),label:l.name,value:u,index:x?re.device+c:s,color:t(l),...os(l)}),!!x&&(h.forEach(b=>{n.push({source:B(l),target:B(b.device),value:b.value}),a(b,c+1)}),d>0)){let b=rt(l,e);o.push({id:B(b),label:b.name,value:d,index:s,color:t(l),...os(l)}),n.push({source:B(l),target:B(b),value:d})}};return r.forEach(i=>a(i,0)),{nodes:o,links:n}},is=r=>r.reduce((e,t)=>t.inside.length>0?Math.max(e,1+is(t.inside)):e,0),B=r=>`device_${r.key}`,Ln=(r,e,t,s)=>(r??[]).map(o=>({id:`source_${o.id}`,label:t[o.id],value:e.reduce((n,a)=>n+(a[o.field]??0),0),index:re.source,color:s(o)})).filter(o=>o.value>0),ss=(r,e,t)=>(r.has(e)||r.set(e,{id:e,name:t||e,value:0}),r.get(e)),Mn=(r,e)=>r?`area_${r.id}`:e?`floor_${e.id}`:pe,os=r=>{let e=r.statistics?.actual_cost;return e?{entityId:e}:{}},ns=(r,e,t)=>[...r.values()].map(s=>({id:`${e}${s.id}`,label:s.name,value:s.value,index:t})),Gn=(r,e)=>[...[...r.values()].map(t=>({source:pe,target:`floor_${t.id}`,value:t.value})),...[...e.values()].map(t=>({source:t.floorId?`floor_${t.floorId}`:pe,target:`area_${t.id}`,value:t.value}))];var cs="hea-distribution-card",ls=`${cs}-editor`,me={cost:{titleKey:"title_distribution",emptyKey:"no_cost_in_period",format:m},energy:{titleKey:"title_distribution_energy",emptyKey:"no_energy_in_period",format:y}},Pn="400px",Hn=88,jn=240,Bn=["auto","horizontal","vertical"],ut=Object.freeze({group_by_floor:!0,group_by_area:!0}),pt=class extends F{static titleKey="title_distribution";static chartTag="ha-sankey-chart";static bearingCard={type:"energy-sankey"};static narrowQuery=I;static cardStyle=`
    ha-sankey-chart { display: block; min-height: 240px; }
  `;static getConfigElement(){return document.createElement(ls)}_isEmpty(){return this._layout().nodes.length===0}_verticalHeight({nodes:e}){let t=new Set(e.map(s=>s.index)).size;return`${Math.max(jn,t*Hn)}px`}_metric(){return me[this._config?.metric]?this._config.metric:"cost"}_titleKey(){return me[this._metric()].titleKey}_emptyKey(){return me[this._metric()].emptyKey}_layout(){let e=te(v(this._hass));return as(this._result?.devices??[],this._labels,{metric:this._metric(),groupByFloor:this._config?.group_by_floor??ut.group_by_floor,groupByArea:this._config?.group_by_area??ut.group_by_area,colour:t=>this._colour(t),deviceColour:t=>t.untracked?this._colour(ee):e.get(t.key)??R[0]})}_chartMarkup(){return"<ha-sankey-chart></ha-sankey-chart>"}_draw(e){e.data=this._layout(),e.vertical=this._isVertical(),e.style.height=this._isVertical()?this._verticalHeight(e.data):Pn;let t=this._chartLocale(),{format:s}=me[this._metric()];e.valueFormatter=o=>s(o,t),this.toggleAttribute("data-vertical",e.vertical)}_isVertical(){let e=this._config?.layout;return e==="vertical"?!0:e==="horizontal"?!1:this._isNarrow()}},mt=class extends _{_extraSchema(){return[{name:"metric",selector:{select:{mode:"dropdown",options:Object.keys(me)}}},{name:"layout",selector:{select:{mode:"dropdown",options:Bn}}},{name:"group_by_floor",selector:{boolean:{}}},{name:"group_by_area",selector:{boolean:{}}}]}setConfig(e){super.setConfig({...ut,...e})}},Wn=()=>{g(ls,mt),f(cs,pt,{name:"Home Energy Advisor: Cost distribution",description:"Where the period's cost went, by floor, room, circuit and device."})};Wn();var ds="hea-filter-card",hs=`${ds}-editor`,Un=[{kind:"area",label:"filter_rooms",id:"areaId",name:"areaName"},{kind:"floor",label:"filter_floors",id:"floorId",name:"floorName"}],W=({kind:r,id:e})=>`${r}:${e??""}`,zn=r=>{let[e,t]=[r.slice(0,r.indexOf(":")),r.slice(r.indexOf(":")+1)];return{kind:e,id:t===""?null:t}},_t=class extends HTMLElement{constructor(){super(),this.attachShadow({mode:"open"})}setConfig(e){this._config=e,this._render()}set hass(e){this._hass=e,A(e).then(()=>this._renderIfChanged()),this._renderIfChanged()}getCardSize(){return 1}static getConfigElement(){return document.createElement(hs)}connectedCallback(){this._render(),this._unfilter??=xe(this._config?.collection_key,()=>this._renderIfChanged())}_signature(){return JSON.stringify([this._allDevices().map(e=>[e.key,e.name,e.areaId,e.areaName,e.floorId,e.floorName,e.labels]),W(se(this._config?.collection_key)),this._labels.filter_rooms])}_renderIfChanged(){this._signature()!==this._drawn&&this._render()}disconnectedCallback(){this._unfilter?.(),this._unfilter=null}get _labels(){return E(this._hass)}_devices(){return v(this._hass).filter(e=>!e.untracked)}_allDevices(){return v(this._hass)}_optionsFor({kind:e,id:t,name:s},o){let n=new Map,a=!1;for(let c of o)c[t]?n.set(c[t],c[s]??c[t]):a=!0;let i=[...n.entries()].map(([c,l])=>({value:W({kind:e,id:c}),text:l})).sort((c,l)=>c.text.localeCompare(l.text));return a&&i.push({value:W({kind:e,id:null}),text:this._labels.filter_unfiled}),i}_labelOptions(e){let t=It(this._hass);return[...new Set(e.flatMap(o=>o.labels??[]))].map(o=>({value:W({kind:"label",id:o}),text:t[o]??o})).sort((o,n)=>o.text.localeCompare(n.text))}_deviceOptions(){return this._allDevices().map(e=>({value:W({kind:"device",id:e.key}),text:e.name})).sort((e,t)=>e.text.localeCompare(t.text))}_groups(){let e=this._devices(),t=Un.map(o=>({label:this._labels[o.label],options:this._optionsFor(o,e)})),s=this._labelOptions(e);return s.length&&t.push({label:this._labels.filter_labels,options:s}),t.push({label:this._labels.filter_devices,options:this._deviceOptions()}),t.filter(o=>o.options.length>0)}_render(){let e=this._labels,t=this._devices();this._drawn=this._signature();let s=t.length?this._control(e):`<p class="message">${e.no_devices}</p>`;this.shadowRoot.innerHTML=`
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
    `;let o=this.shadowRoot.querySelector("select");o&&(o.value=W(se(this._config?.collection_key)),o.addEventListener("change",()=>Lt(this._config?.collection_key,zn(o.value))))}_control(e){let t=this._groups().map(s=>`<optgroup label="${k(s.label)}">${s.options.map(o=>`<option value="${k(o.value)}">${k(o.text)}</option>`).join("")}</optgroup>`).join("");return`<div class="body">
      <span class="label">${e.title_filter}</span>
      <select>
        <option value="${W({kind:"all",id:null})}">${k(e.filter_everything)}</option>
        ${t}
      </select>
    </div>`}},ft=class extends _{},Kn=()=>{g(hs,ft),f(ds,_t,{name:"Home Energy Advisor: Filter",description:"Narrow every Home Energy Advisor card on the page to a room, a floor, a label or one device."})};Kn();var us="hea-installation-card",ps=`${us}-editor`,Yn=[{key:"generationSaved",label:"generation_saved"},{key:"batterySaved",label:"battery_saved"},{key:"exportsEarned",label:"exports_earned"}],gt=class extends O{static titleKey="title_installation";static cardStyle=`
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
  `;static getConfigElement(){return document.createElement(ps)}getCardSize(){return 4}async _fetch(){if(!this._hass||!this._period)return;let e=++this._request;await A(this._hass);let t=G(this._hass);if(!de(this._hass,t)){this._state="empty",this._render();return}try{let s={...gr(t,v(this._hass)),exportsEarned:await this._exportStatistics()},o=await this._hass.callWS({type:"recorder/statistics_during_period",start_time:this._period.start.toISOString(),end_time:this._period.end.toISOString(),statistic_ids:br(s),period:C(this._period),types:["change"]});if(e!==this._request)return;this._earned=vr(o,s,this._period),this._state="ready"}catch(s){if(e!==this._request)return;this._state="error",console.error(`${this.localName}: could not load statistics`,s)}this._render()}async _exportStatistics(){try{let[e,t]=await Promise.all([this._hass.callWS({type:"energy/get_prefs"}),this._hass.callWS({type:"energy/info"})]);return yr(e,t)}catch{return[]}}_content(e){return this._state==="empty"?`<p class="message">${this._labels.no_installation}</p>`:super._content(e)}_body(e){let t=this._earned;return`
      <div class="parts">
        ${Yn.filter(({key:o})=>t?.[o]!==void 0).map(({key:o,label:n})=>this._line("part",o,this._labels[n],e)).join("")}
        ${this._line("total","total",this._labels.total,e)}
      </div>
      <div class="hint">${this._labels.installation_note}</div>`}_line(e,t,s,o){let n=this._earned?.[t],a=w(n,o);return`
      <div class="${e}">
        <span class="label">${s}</span>
        <span class="value${a?` ${a}`:""}" data-figure="${t}">${m(n,o)}</span>
      </div>`}},yt=class extends _{},Vn=()=>{g(ps,yt),f(us,gt,{name:"Home Energy Advisor: What your installation earned",description:"What your generation, battery and exports earned over the selected period, for the whole home."})};Vn();var gs="hea-plans-card",ys=`${gs}-editor`,qn="home_energy_advisor/compare_plans",ms=[{key:"energy",label:"plans_energy",group:"pay"},{key:"daily",label:"plans_daily",figure:"daily_charges",group:"pay"},{key:"export",label:"plans_export",figure:"export_credit",group:"earn"}],Zn=[{key:"pay",label:"plans_you_pay"},{key:"earn",label:"plans_you_earn"}],z=r=>!!(r.incomplete||r.no_price),Xn=r=>!r.follows_prices&&!!(r.rates?.import_market||r.rates?.export_market),_s="grid",Qn=(r,e)=>z(r)||z(e)?(z(r)?1:0)-(z(e)?1:0):r.total-e.total,vt=class extends O{static titleKey="title_plans";static narrowQuery=I;static cardStyle=`${lt}
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
    /* One heading over two rows, so both halves sit where its figures do. */
    .plans thead tr.groups th.without, .plans thead th.without { text-align: right; }
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
    /* A plan's row opens its bill (HEA-300): the whole row takes the pointer,
       and its name is the button a keyboard reaches. */
    tr.figures { cursor: pointer; }
    button.open {
      all: unset;
      cursor: pointer;
      font: inherit;
      color: inherit;
    }
    button.open:focus-visible {
      outline: 2px solid var(--primary-color, #03a9f4);
      outline-offset: 2px;
    }
    button.open::before {
      content: "\u25B8";
      display: inline-block;
      width: 1em;
      color: var(--secondary-text-color);
    }
    button.open[aria-expanded="true"]::before { content: "\u25BE"; }
    /* Context, not money: in the secondary colour unless its verdict colours
       it, never in the red or green of the figure above it. */
    .average { font-size: 0.85em; color: var(--secondary-text-color); }
    /* Allowed to wrap under the import cost, so the column stays as wide as
       its figure rather than its note. */
    td > div > .average { display: inline-block; white-space: normal; max-width: 7em; }
    tr.bill-row > td {
      padding: 0 12px 12px 14px;
      text-align: left;
      white-space: normal;
    }
    .plans .bill {
      width: auto;
      border: none;
      margin-top: var(--hea-space-xs);
      font-size: 0.9em;
    }
    .plans .bill th, .plans .bill td {
      padding: 2px 10px;
      text-align: right;
      white-space: nowrap;
      border: none;
    }
    .plans .bill th { text-align: left; font-weight: normal; }
    .plans .bill thead th {
      background: none;
      color: var(--secondary-text-color);
      font-weight: 400;
      font-size: 0.8em;
    }
    .plans .bill tr.subtotal > *, .plans .bill tr.total > * {
      font-weight: 500;
      border-top: 1px solid var(--divider-color, #e0e0e0);
    }
    /* On a phone the bill fits the three columns the table keeps, rather than
       widening the table past the screen: tighter, and an average may wrap. */
    @media (max-width: 767px) {
      tr.bill-row > td { padding: 0 4px 8px; }
      .plans .bill { font-size: 0.8em; }
      .plans .bill th, .plans .bill td { padding: 2px 5px; }
      .plans .bill .average { white-space: normal; }
    }
  `;static getConfigElement(){return document.createElement(ys)}getCardSize(){return 5}async _fetch(){if(!this._hass||!this._period)return;let e=++this._request;await A(this._hass);try{let t=await this._hass.callWS({type:qn,start_time:this._period.start.toISOString(),end_time:this._period.end.toISOString()});if(e!==this._request)return;this._compared=t,this._state=t?.plans?.length?"ready":"empty"}catch(t){if(e!==this._request)return;this._state="error",console.error(`${this.localName}: could not compare the plans`,t)}this._render()}_content(e){return this._state==="empty"?`<p class="message">${this._labels.no_plans}</p>`:super._content(e)}_body(e){if(!this._compared?.plans)return"";let t=[...this._compared.plans].sort(Qn),s=t.filter(u=>!z(u)),o=s.find(u=>u.current),n=o?.daily_charge_missing?void 0:o,a=s.length>1?s[0]:void 0,i=!this._isNarrow(),c=i?ms:[],l=[this._compared.hours===0?this._labels.plans_no_readings:"",this._currentNote(o),o?.history_from?p(this._labels.plans_current_history_from,{plan:D(o.history_from)}):"",this._labels.plans_note,s.some(u=>u.breakdown)?this._labels.plans_open:"",i?"":this._labels.plans_breakdown_hidden,s.some(Xn)?this._resolution(e):""].filter(Boolean),d=i&&t.some(u=>"without_installation"in u),h={current:n,cheapest:a,parts:c,prices:i,without:d};return`
      ${this._flows(e)}
      ${this._leftOut(e)}
      <div class="scroll">
        <table class="plans">
          <thead>${this._head(h)}</thead>
          ${t.map(u=>this._plan(u,h,e)).join("")}
        </table>
      </div>
      ${l.map(fs).join("")}`}_head({parts:e,prices:t,without:s}){let o=[this._labels.plans_plan,...t?[this._labels.plans_prices]:[]],n=(d,h="")=>`<th${_e(h)}>${d}</th>`,a=[n(this._labels.plans_total,"rule"),...s?[n(this._labels.plans_without,"rule without")]:[],n(this._labels.plans_vs_current)],i=[n(this._labels.plans_plan),...t?[n(this._labels.plans_prices,"prices")]:[],...e.map((d,h)=>n(this._labels[d.label],this._partClasses(d,h))),...a].join("");if(!e.length)return`<tr>${i}</tr>`;let c=Zn.map(d=>{let h=e.filter(x=>x.group===d.key).length;return`<th class="${d.key==="earn"?"rule earn":"rule"}" colspan="${h}">${this._labels[d.label]}</th>`}).join(""),l=s?`<th class="rule"></th><th class="rule without">${this._labels.plans_without_group}</th><th></th>`:`<th colspan="${a.length}" class="rule"></th>`;return`<tr class="groups"><th colspan="${o.length}"></th>${c}${l}</tr>
      <tr>${i}</tr>`}_without(e,t){if(!("without_installation"in e))return'<td class="rule"></td>';let s=xt(-e.without_installation,t),o=e.without_installation-e.total,n=m(Math.abs(o),t),a=w(o,t),i=a==="loss"?p(this._labels.plans_costs_more,{amount:n}):p(this._labels.plans_saves,{amount:n}),c=["saves",a].filter(Boolean).join(" ");return`<td class="${["rule",s.tone].filter(Boolean).join(" ")}" data-figure="without:${e.id}">${s.text}<div class="${c}">${i}</div></td>`}_partClasses(e,t){return[t===0||ms[t-1].group!==e.group?"rule":"",e.group==="earn"?"earn":""].filter(Boolean).join(" ")}_currentNote(e){return e?e.daily_charge_missing?this._labels.plans_current_daily_missing:"":this._labels.plans_no_current}_prices(e,t){let s=e.rates;if(!s)return"<td></td>";let o=ie(t),n=(d,h)=>`<div>${D(d)} <span class="rate">${h}</span></div>`,a=p(this._labels.plans_per_day,{amount:m(s.daily_charge,t)});if(e.follows_prices){let d=[n(this._labels.plans_your_prices,"")];return e.daily_charge_missing||d.push(n(this._labels.plans_daily_rate,a)),`<td class="prices">${d.join("")}</td>`}let i=s.import_market?[n(this._labels.plans_market_price,"")]:s.prices.map(d=>n(d.name,`${Z(d.import,t)} ${o}`)),c=s.export_market?this._labels.plans_market_price:`${Z(s.export,t)} ${o}`;return`<td class="prices">${[...i,n(this._labels.plans_export_rate,c),n(this._labels.plans_daily_rate,a)].join("")}</td>`}_flows(e){if(!this._compared.hours)return"";let t=this._compared.left_out?.length?this._labels.plans_flows_compared:this._labels.plans_flows;return`<div class="flows">${p(t,{imported:y(this._compared.imported_kwh,e),exported:y(this._compared.exported_kwh,e)})}</div>`}_leftOut(e){let t=this._compared.left_out??[];if(!t.length||!this._compared.hours)return"";let s=new Map;for(let n of t){let a=n.kwh!==void 0,i=`${a?"impossible":"missing"}:${n.source}`,c=s.get(i)??{source:n.source,impossible:a,whens:[]};c.whens.push(this._stretch(n,e)),s.set(i,c)}let o=new Map;for(let{source:n,impossible:a,whens:i}of s.values()){let c=i.join(", "),l=a?`impossible:${n}`:`missing:${c}`,d=o.get(l)??{when:c,impossible:a,sources:[]};d.sources.push(n),o.set(l,d)}return[...o.values()].map(n=>`<div class="flows left-out" data-source="${D(n.sources.join(" "))}">${this._leftOutWording(n,e)}</div>`).join("")}_leftOutWording({when:e,impossible:t,sources:s},o){if(t)return p(this._labels.plans_left_out_impossible,{when:e,sensor:this._sensor(s[0])});if(s.length>1){let n=s.map(c=>c===_s?this._labels.plans_your_grid_meters:this._sensor(c)),a=this._labels.plans_left_out_many,i=new Intl.ListFormat(o,{type:"conjunction"}).format(n);return/(^|[.!?]\s+)\{sources\}/.test(a)&&(i=i.charAt(0).toLocaleUpperCase(o)+i.slice(1)),p(a,{when:e,sources:i})}return s[0]===_s?p(this._labels.plans_left_out_meters,{when:e}):p(this._labels.plans_left_out_price,{when:e,sensor:this._sensor(s[0])})}_stretch(e,t){let s=new Date(e.from),o=new Date(e.to),n=we(s,t)===we(o,t),a={from:ke(s,t),to:n?oe(o,t):ke(o,t)};return e.kwh===void 0?p(this._labels.plans_stretch,a):p(this._labels.plans_stretch_kwh,{...a,kwh:y(e.kwh,t)})}_sensor(e){let t=this._hass?.states?.[e]?.attributes?.friendly_name,s=D(e);return t&&t!==e?`${D(t)} (${s})`:s}_plan(e,{current:t,cheapest:s,parts:o,prices:n,without:a},i){let c=this._opened.has(e.id),l=this._name(e,s,c),d=n?this._prices(e,i):"",h=n?2:1,u=h+o.length+2+(a?1:0);if(z(e)){let ge=e.follows_prices?"plans_no_price_current":"plans_no_price",Le=e.no_price?p(this._labels[ge],{sensors:(e.no_price_entities??[]).map(Cs=>this._sensor(Cs)).join(", ")}):this._labels.plans_incomplete;return`<tbody data-plan="${e.id}"><tr>${l}${d}
        <td class="incomplete rule" colspan="${u-h}">${Le}</td></tr></tbody>`}let x=o.map((ge,Le)=>this._part(e,ge,i,this._partClasses(ge,Le))).join(""),b=t&&e!==t?this._difference(e,t,i):"<td></td>",fe=this._exportNotes(e,i).trim(),Ts=c&&e.breakdown?`<tr class="bill-row"><td colspan="${u}">${this._bill(e,i)}</td></tr>`:"";return`<tbody data-plan="${e.id}">
      <tr class="figures">${l}${d}${x}${this._total(e,i)}${a?this._without(e,i):""}${b}</tr>
      ${fe?`<tr class="note"><td colspan="${u}">${fe}</td></tr>`:""}
      ${Ts}
    </tbody>`}_name(e,t,s){let o=[e.current?["current",this._labels.plans_your_plan]:void 0,e===t?["cheapest",this._labels.plans_cheapest]:void 0].filter(Boolean).map(([a,i])=>`<span class="tag ${a}">${i}</span>`).join("");return`<th>${e.breakdown&&!z(e)?`<button class="open" type="button" aria-expanded="${s}">${D(e.name)}</button>`:D(e.name)}${ea(o)}</th>`}get _opened(){return this._openPlans??=new Set,this._openPlans}_afterRender(){this._listening||(this._listening=!0,this.shadowRoot.addEventListener("click",e=>{let s=e.target.closest?.("tr.figures")?.closest("tbody[data-plan]")?.dataset.plan;s&&(this._opened.has(s)?this._opened.delete(s):this._opened.add(s),this._render())}))}_bill(e,t){let{daily:s}=e.breakdown,o=new Intl.NumberFormat(t.language,{maximumFractionDigits:2}),n=[U(t,{name:this._labels.plans_daily,rate:p(this._labels.plans_per_day,{amount:m(s.rate,t)}),used:p(s.days===1?this._labels.plans_day:this._labels.plans_days,{days:o.format(s.days)}),favour:-s.amount,key:"daily"}),...this._importLines(e,t),...this._exportLines(e,t),U(t,{name:this._labels.plans_total,favour:-e.total,key:"total",classes:"total"})],a=["",this._labels.plans_rate,this._labels.plans_used,this._labels.plans_amount].map(c=>`<th>${c}</th>`).join(""),i=e.breakdown.average_import_rate===null?"":fs(this._labels.plans_average_note);return`<table class="bill"><thead><tr>${a}</tr></thead><tbody>${n.join("")}</tbody></table>${i}`}_rate(e,t){return`${Z(e,t)} ${ie(t)}`}_averageOf({kwh:e,amount:t},s){return e?p(this._labels.plans_average,{rate:this._rate(t/e,s)}):""}_importLines(e,t){let{imports:s}=e.breakdown,o=this._averageVerdict(e,t),n=this._labels[e.follows_prices?"plans_your_prices":"plans_market_price"],a=s.map((c,l)=>U(t,{name:c.rate===null?n:c.name||this._labels.plans_unnamed_price,rate:c.rate===null?this._averageOf(c,t):this._rate(c.rate,t),used:y(c.kwh,t),favour:-c.amount,key:"import-"+l})),i=o?.colour?"box-shadow: inset 4px 0 0 "+o.colour.edge:"";return a.push(U(t,{name:this._labels.plans_energy,rate:this._average(e,t,"bill-average",o),used:y(bt(s,"kwh"),t),favour:-e.energy,key:"energy",classes:"subtotal",style:i})),a}_exportLines(e,t){let{exports:s}=e.breakdown,o=s.map((a,i)=>U(t,{name:this._exportName(a,e),rate:a.rate===null?this._averageOf(a,t):this._rate(a.rate,t),used:y(a.kwh,t),favour:a.amount,key:"export-"+i}));s.length>1&&o.push(U(t,{name:this._labels.plans_export,used:y(bt(s,"kwh"),t),favour:bt(s,"amount"),key:"export",classes:"subtotal"}));let n=(e.export_unpaid??0)+(e.export_carried??0);return n>0&&o.push(U(t,{name:this._labels.plans_capped,favour:-n,key:"capped"})),o}_exportName(e,t){return e.rate===null?this._labels[t.follows_prices?"plans_your_export_price":"plans_market_price"]:e.name?e.name:e.beyond_allowance?this._labels.plans_export_beyond:this._labels.plans_export_rate}_average(e,t,s,o=this._averageVerdict(e,t)){if(!o)return"";let n=o.colour?` style="color: ${o.colour.text}"`:"";return`<span class="average" data-figure="${s}"${n} title="${D(o.title)}">${o.text}</span>`}_averageVerdict(e,t){let s=e.breakdown,o=s?.average_import_rate;if(o==null)return;let n=h=>this._rate(h,t),a=s.cheapest_import_rate,i=s.dearest_import_rate,c=i-a,l=c>0?ot((i-o)/c,{dark:J(this)}):void 0,d=e.rates?.import_market?this._labels.plans_average_title_market:this._labels.plans_average_title;return{colour:l,text:p(this._labels.plans_average,{rate:n(o).replace(" ","\xA0")}),title:p(d,{average:n(o),cheapest:n(a),dearest:n(i)})}}_exportNotes(e,t){return[["unpaid",e.export_unpaid,this._labels.plans_export_unpaid],["carried",e.export_carried,this._labels.plans_export_carried]].filter(([,s])=>s>0).map(([s,o,n])=>`<div class="difference" data-figure="export-${s}:${e.id}">${p(n,{amount:m(o,t)})}</div>`).join("")}_resolution(e){let t=this._compared.five_minute_from;if(!t)return this._labels.plans_market_hourly;let s=new Date(t);return s<=this._period.start?this._labels.plans_market_five_minutes:p(this._labels.plans_market_from,{date:ke(s,e)})}_total(e,t){return De(`total:${e.id}`,-e.total,t,"total rule")}_part(e,{key:t,figure:s=t,group:o},n,a=""){if(t==="daily"&&e.daily_charge_missing)return`<td${_e(a)} data-figure="${t}:${e.id}">${this._labels.plans_daily_missing}</td>`;let i=o==="earn"?e[s]:-e[s];if(t!=="energy"||!e.breakdown)return De(`${t}:${e.id}`,i,n,a);let{text:c,tone:l}=xt(i,n),d=[a,l].filter(Boolean).join(" "),h=this._average(e,n,"average:"+e.id),u=h?"<div>"+h+"</div>":"";return`<td${_e(d)} data-figure="${t}:${e.id}">${c}${u}</td>`}_difference(e,t,s){let o=t.total-e.total;return w(o,s)?De(`difference:${e.id}`,o,s,"difference"):`<td class="difference" data-figure="difference:${e.id}">${this._labels.plans_same_short}</td>`}},fs=r=>`<div class="hint">${r}</div>`,bt=(r,e)=>r.reduce((t,s)=>t+s[e],0),Jn=r=>r?` style="${r}"`:"",U=(r,{name:e,rate:t="",used:s="",favour:o,key:n,classes:a="",style:i=""})=>{let c=De("bill-"+n,o,r);return`<tr${_e(a)}><th${Jn(i)}>${D(e)}</th><td>${t}</td><td>${s}</td>${c}</tr>`},_e=r=>r?` class="${r}"`:"",xt=(r,e)=>{let t=w(r,e),s=t==="loss"?-Math.abs(r):Math.abs(r);return{text:m(s,e),tone:t}},De=(r,e,t,s="")=>{let{text:o,tone:n}=xt(e,t),a=[s,n].filter(Boolean).join(" ");return`<td${_e(a)} data-figure="${r}">${o}</td>`},ea=r=>r?`<span class="tags">${r}</span>`:"",D=r=>String(r).replaceAll(/[&<>"']/g,e=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[e]),wt=class extends _{},ta=()=>{g(ys,wt),f(gs,vt,{name:"Home Energy Advisor: Compare tariff plans",description:"What each tariff plan you have entered would have cost over the selected period, for the whole home."})};ta();var xs="hea-self-sufficiency-card",ws=`${xs}-editor`,bs=["energyUsed","energyFromGrid","energyFromGeneration","energyFromBattery","energyFromBatterySolar"],ra={maximumFractionDigits:0},vs=.005,kt=class extends F{static titleKey="title_self_sufficiency";static chartTag="ha-gauge";static bearingCard={type:"energy-self-sufficiency-gauge"};static emptyKey="no_energy_in_period";static cardStyle=`
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
  `;static getConfigElement(){return document.createElement(ws)}getCardSize(){return 4}_isEmpty(){return this._totals().energyUsed<=0}_totals(){return(this._result?.devices??[]).reduce((e,t)=>{for(let s of bs)e[s]+=t[s];return e},Object.fromEntries(bs.map(e=>[e,0])))}_shares(){let e=this._totals(),t=e.energyUsed,s=c=>e[c]/t,o=s("energyFromBatterySolar"),n=s("energyFromGeneration")+o,a=s("energyFromBattery")-o,i=s("energyFromGrid");return{generation:n,storedSolar:o,battery:a,grid:i,unaccounted:Math.max(0,1-n-a-i)}}_body(e){let t=super._body(e);return!this._chartReady||this._isEmpty()?t:`${t}${this._breakdown(e)}`}_gauges(){let e=this._shares(),t=this._totals().energyFromBattery>0;return[{key:"generation",label:this._labels.from_generation,note:e.storedSolar>vs?this._labels.including_stored_solar:"",colour:"var(--energy-solar-color, #ff9800)"},t&&{key:"storedSolar",label:this._labels.of_which_stored_solar,colour:"var(--energy-solar-color, #ff9800)"},t&&{key:"battery",label:this._labels.from_battery_grid,colour:"var(--energy-battery-out-color, #4db6ac)"},{key:"grid",label:this._labels.from_grid,colour:"var(--energy-grid-consumption-color, #488fc2)"}].filter(Boolean).map(s=>({...s,value:e[s.key]}))}_chartMarkup(){let e=K(this._hass),t=p(this._labels.energy_used_came_from,{energy:y(this._totals().energyUsed,e)}),s=this._gauges().map(({key:o,label:n,note:a,colour:i})=>`
        <div class="gauge">
          <ha-gauge data-gauge="${o}" style="--gauge-color: ${i}"></ha-gauge>
          <div class="headline">${n}</div>
          ${a?`<div class="headline">${a}</div>`:""}
        </div>`).join("");return`<div class="intro" data-figure="energy-used">${t}</div>
      <div class="gauges">${s}</div>`}_breakdown(e){let{unaccounted:t}=this._shares();return`${t>vs?`<div class="share">${this._labels.unaccounted}
            <span class="value" data-share="unaccounted">${X(t,e)}</span></div>`:""}<div class="note">${this._labels.self_sufficiency_note}</div>`}_afterRender(){if(!this._chartReady||this._isEmpty())return;let e=Object.fromEntries(this._gauges().map(({key:t,value:s})=>[t,s]));for(let t of this.shadowRoot.querySelectorAll("ha-gauge"))t.hass=this._hass,t.min=0,t.max=100,t.value=e[t.dataset.gauge]*100,t.label="%",t.formatOptions=ra,t.locale=this._hass?.locale}},Et=class extends _{},sa=()=>{g(ws,Et),f(xs,kt,{name:"Home Energy Advisor: Self-sufficiency",description:"What share of the selected period's energy came from the household's own generation."})};sa();var ks="hea-sources-card",Es=`${ks}-editor`,oa=({energyFromGrid:r,energyUsed:e})=>e>0&&r>=0&&r<=e?r/e:void 0,na=[{field:"name",label:"device"},{field:"energyUsed",label:"energy",format:y},{field:"energyFromGrid",label:"grid",format:y},{field:"energyFromGeneration",label:"generation",format:y},{field:"energyFromBattery",label:"battery",format:y},{derive:oa,label:"from_grid",format:X}],Ss={energy_used:{field:"energyUsed",label:"energy_used"},energy_from_grid:{field:"energyFromGrid",label:"from_grid"},energy_from_generation:{field:"energyFromGeneration",label:"from_generation"},energy_from_battery:{field:"energyFromBattery",label:"from_battery"}},St=class extends j{static titleKey="title_sources";static columns=na;static sorts=Ss;static defaultSort="energy_used";static getConfigElement(){return document.createElement(Es)}},$t=class extends _{_extraSchema(){return Ie(Ss,E(this._hass))}},aa=()=>{g(Es,$t),f(ks,St,{name:"Home Energy Advisor: Energy sources",description:"Grid, generation and battery behind each device's energy over the period."})};aa();var As="hea-totals-card",Os=`${As}-editor`,$s=[{key:"actualCost",label:"paid"},{key:"costAtGridPrice",label:"would_have_paid"},{key:"costSavings",label:"saved"}],At=class extends O{static titleKey="title_totals";static cardStyle=`${Se}
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
  `;static getConfigElement(){return document.createElement(Os)}getCardSize(){return 3}_body(e){let t=this._result?.totals;return`<div class="figures">${(this._result?.gridOnly?$s.slice(0,1):$s).map(({key:n,label:a})=>{let i=t?.[n],c=n==="costSavings"?w(i,e):"",l=c?` ${c}`:"";return`
        <div class="figure">
          <span class="label">${$e(a)}${this._labels[a]}</span>
          <span class="value${l}" data-figure="${n}">${m(i,e)}</span>
          ${this._comparedTo(n,i,e)}
        </div>`}).join("")}</div>`}_comparedTo(e,t,s){let o=this._result?.totals?.before?.[e];if(!Number.isFinite(o)||!Number.isFinite(t))return"";let n=V(e,t-o,s);return`<span class="${n?`compare ${n}`:"compare"}" data-compare="${e}">${p(this._labels.compared,{change:Y(t-o,s),before:m(o,s)})}</span>`}},Ot=class extends _{},ia=()=>{g(Os,Ot),f(As,At,{name:"Home Energy Advisor: Totals",description:"What the selected period cost, what it would have cost at grid price, and the difference."})};ia();
