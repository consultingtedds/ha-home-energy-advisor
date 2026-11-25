var As=[4,4,0,0],Os=[0,0,4,4],$t=r=>r!==null&&typeof r=="object"&&!Array.isArray(r),Ts=r=>{let e=$t(r)?r.value:r;return Array.isArray(e)?e[1]:e},De=(r,e)=>{let t=$t(r)?{...r}:{value:r};return{...t,itemStyle:{...t.itemStyle,...e}}},fe=r=>{let e=Math.max(...r.map(({data:s})=>s.length),0),t=r.map(({data:s})=>[...s]);for(let s of Cs(r))for(let o=0;o<e;o++)Fs(t,o,s);return r.map((s,o)=>({...s,data:t[o]}))},Cs=r=>{let e=new Map;return r.forEach((t,s)=>{let o=t.stack??Symbol(s),n=e.get(o);n?n.push(s):e.set(o,[s])}),[...e.values()]},Fs=(r,e,t)=>{let s=!1,o=!1;for(let n=t.length-1;n>=0;n--){let a=t[n],c=r[a][e];if(c===void 0)continue;let i=Ts(c);i?i>0&&!s?(r[a][e]=De(c,{borderRadius:As}),s=!0):i<0&&!o&&(r[a][e]=De(c,{borderRadius:Os}),o=!0):r[a][e]=De(c,{borderWidth:0})}};var At="_energy",Ne="energy_";var Rs=(r,e)=>{let t=r||(e?`${Ne}${e}`:"");return t?t.startsWith(Ne)?`_${t}`:`_${Ne}${t}`:At},Is=(r,e)=>typeof r=="string"&&r.startsWith(At)&&e!==null&&typeof e=="object"&&typeof e.subscribe=="function"&&"start"in e,Ds=(r=new Date)=>{let e=new Date(r);return e.setDate(e.getDate()-30),e.setHours(0,0,0,0),{start:e,end:r,fallback:!0}},Ns=r=>{let e=r?.connection;if(!e)return{};let t={};for(let s of Object.keys(e)){let o;try{o=e[s]}catch{continue}Is(s,o)&&(t[s]=o)}return t},Ls=(r,e)=>{let t=Ns(r),s=Rs(e,r?.panelUrl);if(t[s])return t[s];let[o]=Object.values(t);return o??null},Ms=r=>r?.startCompare&&r?.endCompare?{compare:{start:r.startCompare,end:r.endCompare,mode:r.compareMode}}:{},Ot=(r,e,t)=>{let s=null,o=null,n=0,a=r,c=l=>{if(s)return!0;let d=Ls(l,e);if(!d)return!1;let p=m=>t({start:d.start,end:d.end,fallback:!1,...Ms(m)});return s=d.subscribe(p),p(),!0},i=()=>{o=setTimeout(()=>{o=null,n+=1,!c(a)&&n<40&&i()},250)};return t(Ds()),c(r)||i(),{retry:l=>(l&&(a=l),c(a)),unsubscribe:()=>{o&&clearTimeout(o),o=null;try{typeof s=="function"&&s()}catch{}s=null}}};var ge="sensor.home_energy_advisor_devices",Gs="home_energy_advisor",ye=r=>{if(r?.states?.[ge])return ge;let e=r?.entities;if(!e)return ge;for(let[t,s]of Object.entries(e))if(s?.platform===Gs&&Array.isArray(r?.states?.[t]?.attributes?.devices))return t;return ge},w=(r,e=void 0)=>{let t=r?.states?.[e??ye(r)]?.attributes?.devices;return Array.isArray(t)?t.filter(s=>s?.key).map(Ft):[]},G=(r,e=void 0)=>{let t=r?.states?.[e??ye(r)]?.attributes?.whole_home;return t?.key?Ft(t):null},Tt=(r,e=void 0)=>{let t=r?.states?.[e??ye(r)]?.attributes?.settled_until;if(typeof t!="string")return null;let s=new Date(t);return Number.isNaN(s.getTime())?null:s},Ct=(r,e=void 0)=>{let t=r?.states?.[e??ye(r)]?.attributes?.labels;return t&&typeof t=="object"?t:{}},Ft=r=>({key:r.key,name:r.name||r.key,deviceId:r.device_id??null,untracked:!!r.untracked,statistics:r.statistics??{},areaId:r.area_id??null,areaName:r.area_name??null,floorId:r.floor_id??null,floorName:r.floor_name??null,upstream:r.upstream??null,gross:!!r.gross,labels:Array.isArray(r.labels)?r.labels:[]});var Rt=Object.freeze({kind:"all",id:null}),Hs={area:"areaId",floor:"floorId"},Le=new Map,Me=r=>(Le.has(r)||Le.set(r,{filter:Rt,listeners:new Set}),Le.get(r)),ne=r=>Me(r).filter,be=(r,e)=>{let{listeners:t}=Me(r);return t.add(e),()=>t.delete(e)},It=(r,e)=>{let t=Me(r),s={kind:e?.kind??"all",id:e?.id??null};if(!(s.kind===t.filter.kind&&s.id===t.filter.id)){t.filter=s;for(let o of t.listeners)try{o(s)}catch(n){console.warn("home-energy-advisor: a card could not follow the filter",n)}}},Dt=(r,e)=>{let{kind:t,id:s}=e??Rt;if(t==="all")return!0;if(t==="device")return r.key===s;if(r.untracked)return!1;if(t==="label")return(r.labels??[]).includes(s);let o=Hs[t];return o?(r[o]??null)===s:!0};var Nt={day:"numeric",month:"short",year:"numeric"},K=r=>({language:r?.locale?.language||void 0,currency:r?.config?.currency||void 0,timeFormat:r?.locale?.time_format||void 0,timeZone:r?.locale?.time_zone==="server"?r?.config?.time_zone:void 0}),Ps=({timeFormat:r,language:e})=>{if(r==="language"||r==="system"||!r){let t=r==="system"?void 0:e;return new Date("January 1, 2023 22:00:00").toLocaleString(t).includes("10")}return r==="12"},ae=(r,e)=>new Intl.DateTimeFormat(e.language,{hour:"numeric",minute:"2-digit",hourCycle:Ps(e)?"h12":"h23",timeZone:e.timeZone}).format(r),ve=(r,e)=>new Intl.DateTimeFormat(e.language,{...Nt,timeZone:e.timeZone}).format(r),we=(r,e)=>`${ve(r,e)}, ${ae(r,e)}`,js=(r,e)=>new Intl.DateTimeFormat(e.language,{weekday:"short",month:"short",day:"numeric",timeZone:e.timeZone}).format(r),Bs={hour:3600*1e3},Lt=(r,e,t)=>{let s=Bs[e];if(!s)return js(r,t);let o=new Date(r.getTime()+s);return`${ae(r,t)} \u2013 ${ae(o,t)}`},u=(r,{language:e,currency:t})=>typeof r!="number"||!Number.isFinite(r)?"-":new Intl.NumberFormat(e,{...Mt(t),signDisplay:"negative"}).format(r),Mt=r=>r?Ge(r):{minimumFractionDigits:2,maximumFractionDigits:2},Ge=r=>({style:"currency",currency:r,currencyDisplay:"narrowSymbol"}),Gt=(r,{language:e,currency:t}={})=>{let o=10**new Intl.NumberFormat(e,Mt(t)).resolvedOptions().maximumFractionDigits;return Math.round(r*o)/o},Y=(r,{language:e,currency:t})=>{if(typeof r!="number"||!Number.isFinite(r))return"-";let s=t?{...Ge(t),signDisplay:"exceptZero"}:{minimumFractionDigits:2,maximumFractionDigits:2,signDisplay:"exceptZero"};return new Intl.NumberFormat(e,s).format(r)},Us=new Set(["actualCost","costAtGridPrice","energyUsed"]),Ws=new Set(["costSavings"]),x=(r,e)=>{if(typeof r!="number"||!Number.isFinite(r))return"";let t=Gt(r,e);return t===0?"":t>0?"gain":"loss"},zs=new Set(["actualCost","costAtGridPrice","costSavings"]),V=(r,e,t)=>{if(typeof e!="number"||!Number.isFinite(e))return"";let s=zs.has(r)?Gt(e,t):e;return s===0?"":Us.has(r)?s<0?"gain":"loss":Ws.has(r)?s>0?"gain":"loss":""},q=(r,e)=>{if(!Array.isArray(r))return"-";let[t,s]=r;if(![t,s].every(a=>Number.isFinite(a)))return"-";if(t===s)return u(t,e);let[o,n]=t<=s?[t,s]:[s,t];return`${u(o,e)} - ${u(n,e)}`},v=(r,{language:e})=>typeof r!="number"||!Number.isFinite(r)?"-":`${new Intl.NumberFormat(e,{maximumFractionDigits:1}).format(r)} kWh`,Ht={EUR:{symbol:"c",per:100},USD:{symbol:"\xA2",per:100},GBP:{symbol:"p",per:100}},ie=(r,{language:e})=>typeof r!="number"||!Number.isFinite(r)?"-":new Intl.NumberFormat(e,{minimumFractionDigits:r===0?0:2,maximumFractionDigits:2}).format(r),ce=({language:r,currency:e})=>e?Pt(r,e):"",Pt=(r,e)=>new Intl.NumberFormat(r,Ge(e)).formatToParts(0).find(t=>t.type==="currency")?.value??"",xe=({language:r,currency:e})=>{if(!e)return"/kWh";let t=Ht[e];return`${t?t.symbol:Pt(r,e)}/kWh`},ke=(r,{language:e,currency:t})=>{if(typeof r!="number"||!Number.isFinite(r))return"-";let s=t?Ht[t]:void 0;return new Intl.NumberFormat(e,{minimumFractionDigits:s?1:0,maximumFractionDigits:s?2:3}).format(s?r*s.per:r)},Z=(r,{language:e})=>typeof r!="number"||!Number.isFinite(r)?"-":new Intl.NumberFormat(e,{style:"percent",maximumFractionDigits:0}).format(r),k=r=>String(r).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#39;"),le=(r,{language:e})=>r?new Intl.DateTimeFormat(e,Nt).formatRange(r.start,r.end):"";var Bt="common",Ut="home_energy_advisor",jt=`component.${Ut}.${Bt}.card_`,Pe=Object.freeze({paid:"Paid",would_have_paid:"Would have paid",saved:"Saved",lost:"Lost",range_column:"Paid (min-max)",range_note:"Paid (min-max) is the widest range these readings allow, not a typical error: a meter that reports every 30-90 minutes leaves the exact moment of use unknown.",range_whole_home:"What you paid could honestly sit between {range} - the widest these readings allow, not a typical error.",range_device:"What you paid could be between {range}.",range_note_rollover:"Hover over or tap a figure in Paid to see the range it could honestly have been. That range is the widest these readings allow, not a typical error: a meter that reports every 30-90 minutes leaves the exact moment of use unknown.",forgone_column:"Could have earned",forgone_note:"Could have earned is what the generation each device used could have earned had you exported it instead, at your export rate at the time. It is money you did not receive, not money you paid, and it is not part of Paid.",forgone_hidden_note:"Could have earned, what the generation each device used could have earned had you exported it instead, is shown on a wider screen.",device_costs_note:"The solid part of each bar is what the device cost. The whole bar is what it would have cost had all its energy come from the grid, at your grid price at the time.",compared:"{change} vs {before}",compared_period:"{period} vs {compared}",saved_share:"{percent} of what you would have paid was saved.",lost_share:"{percent} more was paid than the grid would have cost.",change:"Change",compared_series:"Earlier period",device:"Device",energy:"Energy",rate:"Rate",total:"Total",grid:"Grid",generation:"Generation",battery:"Battery",from_grid:"From the grid",from_generation:"From generation",from_battery:"From the battery",from_battery_grid:"From battery (grid)",of_which_stored_solar:"Of which stored solar",energy_used_came_from:"Where the {energy} of energy used came from",including_stored_solar:"including stored solar",energy_used:"Energy used",unaccounted:"Unaccounted",self_sufficiency_note:"Solar stored in the battery counts as your own. Battery energy charged from the grid does not, and is shown on its own.",household:"Household",generation_saved:"Generation saved",battery_saved:"Battery saved",exports_earned:"Exports earned",installation_note:"For the whole home: your own generation, your battery and your exports, measured against your current tariff. What the battery lost is taken off what it saved.",no_installation:"There is no generation or battery here, so nothing for an installation to have earned.",title_installation:"What your installation earned",title_plans:"Compare tariff plans",tab_summary:"Summary",tab_devices:"Devices",tab_tariffs:"Tariffs",plans_your_plan:"Current plan",plans_cheapest:"Cheapest",plans_on_now:"Your plan",plans_since:"Your plan since {date}",plans_until:"Your plan until {date}",plans_from:"Your plan from {date}",plans_archived_one:"{count} plan is archived and not shown. To bring it back, untick Archived in its settings.",plans_archived_many:"{count} plans are archived and not shown. To bring one back, untick Archived in its settings.",plans_energy:"Import cost",plans_export:"Export income",plans_daily:"Daily charges",plans_plan:"Plan",plans_you_pay:"What you pay",plans_you_earn:"What you earn",plans_market_price:"Market price",plans_export_rate:"Export",plans_per_day:"{amount}/day",plans_total:"Total",plans_without_group:"Buying everything",plans_without:"from the grid",plans_saves:"your installation saves you {amount}",plans_costs_more:"your installation costs you {amount} more",plans_vs_current:"vs current plan",plans_same_short:"The same",plans_in_credit:"{amount} in credit",plans_cheaper:"{amount} cheaper",plans_dearer:"{amount} dearer",plans_flows:"Imported {imported} and exported {exported} in this period.",plans_flows_compared:"Imported {imported} and exported {exported} in the hours compared.",plans_flows_import:"Imported {imported} in this period.",plans_flows_import_compared:"Imported {imported} in the hours compared.",plans_breakdown_hidden:"Import cost, export income and daily charges are shown on a wider screen.",plans_breakdown_hidden_import:"Import cost and daily charges are shown on a wider screen.",plans_breakdown_hidden_demand:"Import cost, export income, daily charges and demand charges are shown on a wider screen.",plans_breakdown_hidden_import_demand:"Import cost, daily charges and demand charges are shown on a wider screen.",plans_incomplete:"Not every hour has a price, so it cannot be compared. Edit the plan to finish its bands.",plans_note:"For the whole home: each plan priced at the electricity you actually imported and exported, as if your battery had run the same way. Prices are compared as you entered them.",plans_no_readings:"Your grid meters recorded nothing in this period, so there is nothing to compare.",plans_no_current:"Your current plan could not be priced for this period, so no plan is compared with it.",plans_current_daily_missing:"Plans are compared with your current plan once it has its daily charge: Settings > Repairs asks for it.",plans_your_prices:"The prices you pay",plans_your_export_price:"Your export price",plans_daily_missing:"Not given yet",plans_demand:"Demand charges",plans_demand_missing:"No reading",plans_demand_note:"Demand charges are counted in Buying everything from the grid too, so what your installation saves leaves out what it saved by lowering your peak.",plans_no_price:"{sensors} recorded no statistics in this period, so it cannot be compared. Check it in Developer Tools > Statistics: a price sensor needs the state class measurement for Home Assistant to keep them.",plans_no_price_current:"{sensors} has no statistics for some of this period, so your current plan cannot be priced. To price those hours, add the plans you were on, each with the day it started, under Plans you've been on, in your current plan's settings. To keep its statistics from now on, give the sensor the state class measurement.",plans_current_history_from:"Hours your price sensors have no statistics for are priced at the plan you were on that day: {plans}.",plans_export_unpaid:"{amount} of export not paid: capped at each month's energy cost.",plans_export_carried:"{amount} of export carried forward and not yet used.",plans_left_out_meters:"Left out of every plan, daily charges included: {when}. Your grid meters recorded nothing then.",plans_left_out_price:"Left out of every plan, daily charges included: {when}. {sensor} recorded no statistics then. Check it in Developer Tools > Statistics.",plans_left_out_many:"Left out of every plan, daily charges included: {when}. {sources} recorded nothing then. Check any sensor named in Developer Tools > Statistics.",plans_your_grid_meters:"your grid meters",plans_stretch:"{from} to {to}",plans_stretch_kwh:"{from} to {to} ({kwh})",plans_left_out_impossible:"Left out of every plan, daily charges included: {when}. {sensor} recorded more than a home can use in an hour then. Correct it from Settings > Repairs.",plans_open:"Select a plan to see its total line by line, as a bill lists it.",plans_rate:"Rate",plans_used:"Used",plans_amount:"Amount",plans_day:"{days} day",plans_days:"{days} days",plans_unnamed_price:"Price",plans_export_beyond:"Export beyond its allowance",plans_capped:"Not paid under the export cap",plans_average:"average {rate}",plans_average_title:"{average} on average: your cheapest price is {cheapest} and your dearest {dearest}.",plans_average_title_market:"{average} on average: the cheapest hour you imported in was {cheapest}, and the dearest {dearest}.",plans_average_note:"The average is the import cost divided by the kWh imported: worked out from your use, not one of the plan's prices.",plans_market_hourly:"Market prices are applied hour by hour, at each hour's average.",plans_market_five_minutes:"Market prices are applied five minutes at a time.",plans_market_from:"Market prices are applied five minutes at a time from {date}, and hour by hour, at each hour's average, before that.",no_plans:"No tariff plans yet. Add one from the Home Energy Advisor integration, with Add tariff plan.",title_totals:"Cost summary",title_devices:"Cost by device",title_device_costs:"What each device cost",title_cost_over_time:"Cost over time",title_sources:"Where the energy came from",title_self_sufficiency:"Self-sufficiency",title_distribution:"Where the cost went",title_distribution_energy:"Where the energy went",no_devices:"No devices are being tracked yet.",no_devices_in_filter:"No tracked device matches what the page is showing.",title_filter:"Show",filter_everything:"Everything",filter_rooms:"Rooms",filter_floors:"Floors",filter_labels:"Labels",filter_devices:"Devices",filter_unfiled:"Not in one",device_untracked:"Untracked",hourly_shape_estimate:"One device's hourly shape is an estimate: each meter reading is spread across the hours it spanned, so cost may not land in the hour the energy was used.",still_accruing:"The last interval is still being counted, so its bar will grow. Figures are complete about twenty minutes behind the clock, which is how long meters are given to report.",statistics_failed:"Statistics could not be loaded.",loading:"Loading\u2026",no_picker:"Add an Energy date picker card to choose the range.",chart_not_loaded:"Home Assistant's chart component is not loaded. Adding any energy or statistics card to this dashboard will load it.",no_cost_in_period:"No cost recorded in this period.",no_energy_in_period:"No energy recorded in this period.",editor_title:"Title",editor_collection_key:"Energy period (collection key)",editor_devices:"Devices (all, if none are chosen)",editor_sort_by:"Order by",editor_layout:"Layout",editor_metric:"Measure by",editor_group_by_floor:"Group by floor",editor_group_by_area:"Group by area",editor_range:"Show the cost range as",editor_range_auto:"Automatic: a column where there is room",editor_range_rollover:"A rollover on Paid",editor_range_column:"Its own column"}),He=new Map,Wt=new Map,zt=r=>r?.locale?.language||r?.language||"en",A=r=>{let e=zt(r);return He.has(e)||He.set(e,Ks(r,e).then(t=>(Wt.set(e,t),t))),He.get(e)},Ks=async(r,e)=>{try{let{resources:t}=await r.callWS({type:"frontend/get_translations",language:e,category:Bt,integration:[Ut]});return Object.freeze({...Pe,...Ys(t)})}catch(t){return console.warn("home-energy-advisor: falling back to English labels",t),Pe}},E=r=>Wt.get(zt(r))??Pe,Ys=r=>Object.fromEntries(Object.entries(r??{}).filter(([e,t])=>e.startsWith(jt)&&t).map(([e,t])=>[e.slice(jt.length),t])),h=(r,e)=>Object.entries(e).reduce((t,[s,o])=>t.replaceAll(`{${s}}`,o),r);var S=Object.freeze({energyUsed:"energy_used",actualCost:"actual_cost",costAtGridPrice:"cost_at_grid_price",energyFromGrid:"energy_from_grid",energyFromGeneration:"energy_from_generation",energyFromBattery:"energy_from_battery",energyFromBatterySolar:"energy_from_battery_solar",forgoneExport:"forgone_export"}),L=Object.freeze({costFloor:"lowest_possible_cost",costCeiling:"highest_possible_cost"}),je=()=>Object.fromEntries(Object.keys(S).map(r=>[r,0])),qt=1440*60*1e3,Zt={hour:3600*1e3,day:qt},Vs=2,X=(r,e)=>r?.statistics?.[e],de=r=>S.costAtGridPrice in(r?.statistics??{}),Xt=(r,e,t,s=!1)=>e==="costAtGridPrice"&&!de(r)?X(r,S.actualCost):e==="energyFromGrid"&&s?X(r,S.energyUsed):X(r,t),qs=r=>[S.energyFromGrid,S.energyFromGeneration,S.energyFromBattery].some(e=>e in(r?.statistics??{})),Zs=r=>r.length>0&&!r.some(qs),Q=(r,e=[])=>{let t=w(r);return Zs(t.length?t:e)},Xs=(r,e)=>{let t=r.flatMap(s=>[...Object.values(S),...Object.values(L)].map(o=>X(s,o)).filter(Boolean));return!e?.statistics||r.length===0?t:[...t,...Object.values(L).map(s=>X(e,s)).filter(Boolean)]},Qt=(r,e)=>{if(!e)return r;let t=new Map(e.devices.map(s=>[s.key,s]));return{...r,totals:{...r.totals,before:e.totals},devices:r.devices.map(s=>({...s,before:t.get(s.key)})),seriesBefore:Qs(e.series,r.period,e.period)}},Qs=(r,e,t)=>{if(!r?.length)return;let s=e.start.getTime()-t.start.getTime();return r.map(o=>({...o,start:new Date(o.start.getTime()+s),actualStart:o.start}))},C=({start:r,end:e})=>e-r>Vs*qt?"day":"hour",Kt=(r,e,t)=>{if(e!=="day")return new Date(r.getTime()+t*Zt.hour);let s=new Date(r);return s.setDate(s.getDate()+t),s},Jt=(r,e)=>{if(!r.length||!e)return r;let t=C(e),s=new Map(r.map(a=>[a.start.getTime(),a])),o=r[0].start,n=[];for(let a=0;;a--){let c=Kt(o,t,a);if(c.getTime()<e.start.getTime())break;n.push(s.get(c.getTime())??Yt(c))}n.reverse();for(let a=1;;a++){let c=Kt(o,t,a);if(c.getTime()>=e.end.getTime())break;n.push(s.get(c.getTime())??Yt(c))}return n},Yt=r=>({...je(),start:r,costSavings:0,accruing:!1}),Vt=new WeakMap,Js=(r,e)=>{let t=r.connection??r,s=Vt.get(t);s||(s=new Map,Vt.set(t,s));let o=JSON.stringify(e),n=s.get(o);if(n)return n;let a=r.callWS(e).finally(()=>s.delete(o));return s.set(o,a),a},Be=async(r,e,t,s,o=null)=>{let n=Xs(e,s),a=n.length?await Js(r,{type:"recorder/statistics_during_period",start_time:t.start.toISOString(),end_time:t.end.toISOString(),statistic_ids:n,period:C(t),types:["change"]}):{},c=Q(r,e),i=ro(e.map(l=>to(l,a,t,c)));return{period:t,gridOnly:c,devices:i,totals:oo(i),wholeHome:er(s,a,t),series:eo(e,a,t,o,c)}},er=(r,e,t)=>{if(!r)return;let s={};for(let[o,n]of Object.entries(L)){let a=e?.[X(r,n)];if(!Array.isArray(a))return;s[o]=rr(a,t)}return s},eo=(r,e,t,s,o)=>{let n=new Map,a=new Set(r.filter(i=>i.gross).map(i=>i.key));for(let i of r.filter(l=>!a.has(l.upstream)))for(let[l,d]of Object.entries(S)){let p=e?.[Xt(i,l,d,o)];for(let m of tr(p,t)){let _=n.get(m.start)??je();_[l]+=m.change,n.set(m.start,_)}}let c=Zt[C(t)]??0;return[...n.entries()].sort(([i],[l])=>i-l).map(([i,l])=>({...l,start:new Date(i),costSavings:l.costAtGridPrice-l.actualCost,accruing:s?i+c>s.getTime():!1}))},to=(r,e,t,s)=>{let o=Object.fromEntries(Object.entries(S).map(([n,a])=>[n,rr(e?.[Xt(r,n,a,s)],t)]));return{...r,...o,...er(r,e,t),costSavings:o.costAtGridPrice-o.actualCost}},ro=r=>{let e=new Map;for(let t of r)t.upstream&&e.set(t.upstream,[...e.get(t.upstream)??[],t]);return r.map(t=>{if(!t.gross)return t;let s={...t};for(let o of Object.keys(S)){let n=(e.get(t.key)??[]).reduce((a,c)=>a-c[o],t[o]);s[o]=Math.abs(n)<so(o)?0:n}return s.costSavings=s.costAtGridPrice-s.actualCost,s})},so=r=>r.startsWith("energy")?5e-4:.005,tr=(r,{start:e,end:t})=>{if(!Array.isArray(r))return[];let s=[];for(let o of r){let n=new Date(o.start).getTime();n<e.getTime()||n>=t.getTime()||typeof o.change=="number"&&s.push({start:n,change:o.change})}return s},rr=(r,e)=>tr(r,e).reduce((t,s)=>t+s.change,0),oo=r=>({...r.reduce((t,s)=>{for(let o of Object.keys(t))t[o]+=s[o];return t},{...je(),costSavings:0}),...no(r)}),no=r=>{let e=Object.keys(L);return!r.length||!r.every(t=>e.every(s=>s in t))?{}:Object.fromEntries(e.map(t=>[t,r.reduce((s,o)=>s+o[t],0)]))};var ao=`
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
`,io=`
  .loss { color: var(--error-color, #db4437); }
  .gain { color: var(--success-color, #4caf50); }
`,I="(max-width: 767px)",O=class extends HTMLElement{static cardStyle="";static narrowQuery="";static titleKey="";_titleKey(){return this.constructor.titleKey}get _labels(){return E(this._hass)}constructor(){super(),this.attachShadow({mode:"open"}),this._state="loading",this._request=0}setConfig(e){if(e.devices!==void 0&&!Array.isArray(e.devices))throw new Error("`devices` must be a list of device keys");this._config=e,this._render()}set hass(e){this._hass=e,this._subscription?this._subscription.retry(e):this._subscribe(),this._refetchIfDevicesChanged()}connectedCallback(){this._render(),this._hass&&!this._subscription&&this._subscribe(),this._watchScreen()}disconnectedCallback(){this._subscription?.unsubscribe(),this._subscription=null,this._unfilter?.(),this._unfilter=null,this._screen?.removeEventListener?.("change",this._onScreenChange),this._screen=null}_watchScreen(){let{narrowQuery:e}=this.constructor;!e||this._screen||(this._screen=globalThis.matchMedia?.(e),this._onScreenChange??=()=>this._render(),this._screen?.addEventListener?.("change",this._onScreenChange))}_isNarrow(){return!!globalThis.matchMedia?.(I)?.matches}_subscribe(){this._subscription=Ot(this._hass,this._config?.collection_key,e=>{this._period=e,this._scheduleFetch()}),this._unfilter=be(this._config?.collection_key,()=>this._scheduleFetch())}_scheduleFetch(){this._fetchPending||(this._fetchPending=!0,queueMicrotask(()=>{this._fetchPending=!1,this._fetch()}))}_refetchIfDevicesChanged(){let e=this._devices().map(t=>t.key).join(",");e!==this._deviceKeys&&(this._deviceKeys=e,this._period&&this._scheduleFetch())}_devices(){let e=w(this._hass),t=this._config?.devices,s=t?e.filter(n=>t.includes(n.key)):e,o=this._filter();return s.filter(n=>Dt(n,o))}_filter(){return ne(this._config?.collection_key)}_isFiltered(){return!!this._config?.devices||this._filter().kind!=="all"}async _fetch(){if(!this._hass||!this._period)return;let e=this._devices(),t=++this._request;if(await A(this._hass),e.length===0){this._state="empty",this._render();return}let s=this._isFiltered()?void 0:G(this._hass);try{let o=Tt(this._hass),[n,a]=await Promise.all([Be(this._hass,e,this._period,s,o),this._period.compare?Be(this._hass,e,this._period.compare,s):void 0]);if(t!==this._request)return;this._result=Qt(n,a),this._state="ready"}catch(o){if(t!==this._request)return;this._state="error",console.error(`${this.localName}: could not load statistics`,o)}this._render()}_render(){let e=K(this._hass);this.shadowRoot.innerHTML=`
      <style>${ao}${this.constructor.cardStyle}${io}</style>
      <ha-card>
        <div class="body" data-state="${this._state}">${this._content(e)}</div>
      </ha-card>
    `;let t=this._config?.title??this._labels[this._titleKey()];t&&this._writeHeader(t,e),this._afterRender()}_writeHeader(e,t){let s=this.shadowRoot.querySelector("ha-card"),o=this._headerChip(t);if(o===void 0){s.setAttribute("header",e);return}s.insertAdjacentHTML("afterbegin",`<div class="card-header" style="display: flex; justify-content: space-between;
         align-items: center; gap: var(--hea-space-s); padding-bottom: 0;">
        <span class="title">${k(e)}</span>
        <span class="chip">${k(o)}</span>
      </div>`)}_headerChip(){}_afterRender(){}_content(e){return this._state==="loading"?`<p class="message" role="status">${this._labels.loading}</p>`:this._state==="empty"?`<p class="message">${this._labels.no_devices}</p>`:this._state==="error"?`<p class="message">${this._labels.statistics_failed}</p>`:`${this._body(e)}${this._caption(e)}`}_caption(e){let t=this._period?.fallback?`<div class="hint">${this._labels.no_picker}</div>`:"";return`<div class="period">${this._periodLabel(e)}</div>${t}`}_periodLabel(e){let t=le(this._period,e),s=this._period?.compare;return s?h(this._labels.compared_period,{period:t,compared:le(s,e)}):t}},y=(r,e,{name:t,description:s})=>{customElements.get(r)||customElements.define(r,e),globalThis.customCards=globalThis.customCards??[],globalThis.customCards.some(o=>o.type===r)||globalThis.customCards.push({type:r,name:t,description:s})};var co={title:"editor_title",collection_key:"editor_collection_key",devices:"editor_devices",sort_by:"editor_sort_by",layout:"editor_layout",metric:"editor_metric",group_by_floor:"editor_group_by_floor",group_by_area:"editor_group_by_area",range:"editor_range"},f=class extends HTMLElement{constructor(){super(),this.attachShadow({mode:"open"})}setConfig(e){this._config=e,this._render()}set hass(e){this._hass=e,this._render(),A(e).then(()=>this._render())}_extraSchema(){return[]}_render(){if(!this._config)return;let e=this.shadowRoot.querySelector("ha-form");e||(e=document.createElement("ha-form"),e.computeLabel=t=>E(this._hass)[co[t.name]]??t.name,e.addEventListener("value-changed",t=>this._report(t.detail.value)),this.shadowRoot.append(e)),e.hass=this._hass,e.data=this._config,e.schema=this._schema()}_schema(){return[{name:"title",selector:{text:{}}},{name:"collection_key",selector:{text:{}}},{name:"devices",selector:{select:{multiple:!0,mode:"list",options:w(this._hass).map(e=>({value:e.key,label:e.name}))}}},...this._extraSchema()]}_report(e){this.dispatchEvent(new CustomEvent("config-changed",{detail:{config:lo({...this._config,...e})},bubbles:!0,composed:!0}))}},lo=r=>Object.fromEntries(Object.entries(r).filter(([,e])=>e!==""&&e!==void 0&&e!==null&&!(Array.isArray(e)&&e.length===0))),b=(r,e)=>{customElements.get(r)||customElements.define(r,e)};var F=class extends O{static chartTag="ha-chart-base";static bearingCard={type:"statistics-graph",entities:[]};static emptyKey="no_cost_in_period";static chartHeight="clamp(320px, 40vw, 480px)";static cardStyle=`
    ha-chart-base { display: block; --chart-max-height: none; }
  `;constructor(){super(),this._chartReady=!!customElements.get(this.constructor.chartTag)}getCardSize(){return 6}connectedCallback(){super.connectedCallback(),this._chartReady||this._loadChartComponent()}async _loadChartComponent(){let{chartTag:e,bearingCard:t}=this.constructor;customElements.whenDefined(e).then(()=>{this._chartReady=!0,this._render()});try{await(await globalThis.loadCardHelpers?.())?.createCardElement(t)}catch(s){console.warn(`${e}: could not be loaded`,s)}}_isEmpty(){return(this._result?.series??[]).length===0}_body(){return this._chartReady?this._isEmpty()?`<p class="message">${this._labels[this._emptyKey()]}</p>`:this._chartMarkup():`<p class="message">${this._labels.chart_not_loaded}</p>`}_emptyKey(){return this.constructor.emptyKey}_chartMarkup(){return'<ha-chart-base chart-type="bar"></ha-chart-base>'}_afterRender(){let e=this.shadowRoot.querySelector(this.constructor.chartTag);e&&(e.hass=this._hass,this._draw(e))}_chartHeight(){return this.constructor.chartHeight}_draw(e){e.height=this._chartHeight(),e.data=this._series(),e.options=this._options(this._chartLocale())}_chartLocale(){return K(this._hass)}_colour({variable:e,fallback:t}){return getComputedStyle(this).getPropertyValue(e).trim()||t}};var ho=/^#([\da-f]{3}|[\da-f]{6})$/i,uo=/^rgba?\(([^)]+)\)$/i,Ue=r=>{let e=ho.exec(String(r).trim());if(e){let o=e[1];return(o.length===3?[...o].map(a=>a+a):[0,2,4].map(a=>o.slice(a,a+2))).map(a=>Number.parseInt(a,16))}let t=uo.exec(String(r).trim());if(!t)return;let s=t[1].split(/[\s,/]+/).filter(Boolean).slice(0,3).map(Number);return s.length===3&&s.every(Number.isFinite)?s:void 0},D=(r,e)=>{let t=Ue(String(r).trim());return t?`rgba(${t.join(", ")}, ${e})`:r},po=([r,e,t])=>(.2126*r+.7152*e+.0722*t)/255,J=r=>{let e=Ue(mo(r));return e?po(e)>.5:!1},mo=r=>{let e=[r,r?.ownerDocument?.documentElement].filter(Boolean);for(let t of e){let s=getComputedStyle(t),o=s.getPropertyValue("--primary-text-color").trim()||s.color;if(Ue(o))return o}return""};var sr=Object.freeze({variable:"--primary-color",fallback:"#03a9f4"}),or=Object.freeze({variable:"--success-color",fallback:"#4caf50"}),_o=Object.freeze({paid:"paid",would_have_paid:"would-have-paid",saved:"saved"}),Ee=`
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
`,Se=r=>{let e=typeof r=="string"?_o[r]:void 0;return e?`<span class="swatch ${e}" aria-hidden="true"></span>`:""};var M=(r,e,t,{bold:s=!1}={})=>{let o=document.createElement("div");o.style.display="flex",o.style.justifyContent="space-between",o.style.gap="16px",s&&(o.style.fontWeight="bold");let n=document.createElement("span");n.textContent=r;let a=document.createElement("span");return a.textContent=e,a.style.fontVariantNumeric="tabular-nums",t&&(a.style.color=t),o.append(n,a),o},fo=r=>{let e=document.createElement("span");return e.style.display="inline-block",e.style.width="10px",e.style.height="10px",e.style.borderRadius="10px",e.style.marginInlineEnd="4px",e.style.verticalAlign="middle",e.style.backgroundColor=r,e},nr=(r,e,t,s)=>{let o=M(e,t,s);return o.firstChild.prepend(fo(r)),o},$e=r=>{let e=document.createElement("div");return e.textContent=r,e.style.fontWeight="bold",e.style.textAlign="center",e.style.marginBottom="4px",e},ar=r=>{let e=document.createElement("div");return e.textContent=r,e.style.marginTop="4px",e.style.maxWidth="260px",e.style.whiteSpace="normal",e.style.opacity="0.7",e};var dr="hea-cost-over-time-card",hr=`${dr}-editor`,go={hour:3600*1e3,day:1440*60*1e3},yo=50,bo=.5,vo=(r,e)=>{if(!r.length||!e)return 0;let t=go[C(e)]??0,s=r.length>=2?r[1].start.getTime()-r[0].start.getTime():void 0;return(s?Math.min(s,t):t)/2},H={paid:{id:"paid",name:"paid",...sr},saved:{id:"saved",name:"saved",...or}},ur={variable:"--error-color",fallback:"#db4437"},wo={gain:{variable:"--success-color",fallback:"#4caf50"},loss:ur},We=r=>r.value?.[1]??0,xo=r=>r.value?.[2],ko=.45,Ae={id:"before",name:"compared_series",variable:"--secondary-text-color",fallback:"#727272"},ze=class extends F{static titleKey="title_cost_over_time";static getConfigElement(){return document.createElement(hr)}_series(){let e=Jt(this._result?.series??[],this._result?.period),t=this._colour(ur),s=this._labels,o=this._result?.seriesBefore,n=vo(e,this._result?.period),a={...lr(H.paid,this._colour(H.paid),s),data:e.map(i=>ir(i,cr(i,i.actualCost,n)))},c={...lr(H.saved,this._colour(H.saved),s),data:e.map(i=>{let l=cr(i,i.costSavings,n),d=i.costSavings<0?pr(t):void 0;return ir(i,l,d)})};return[...fe(this._result?.gridOnly?[a]:[a,c]),...o?.length?[{id:Ae.id,name:s[Ae.name],type:"line",symbol:"none",lineStyle:{type:"dashed",width:2},itemStyle:{color:this._colour(Ae)},data:o.map(i=>[i.start.getTime()+n,i.costAtGridPrice])}]:[]]}_caption(e){return`${super._caption(e)}${this._stillAccruingNote()}`+this._accrualNote()}_stillAccruingNote(){return(this._result?.series??[]).some(e=>e.accruing)?`<div class="hint">${this._labels.still_accruing}</div>`:""}_accrualNote(){return this._devices().length!==1||!this._period||C(this._period)!=="hour"?"":`<div class="hint">${this._labels.hourly_shape_estimate}</div>`}_tooltipFor(e,t){let s=(Array.isArray(e)?e:[e]).filter(i=>i.componentSubType==="bar"),o=s.filter(i=>We(i)!==0);if(!o.length)return;let n=this._bucketAt(s.map(xo).find(i=>i!==void 0)),a=document.createElement("div");a.append($e(this._spanOf(n,t)));for(let i of o)a.append(this._tooltipRowFor(i,t));let c=s.reduce((i,l)=>i+We(l),0);return o.length>1&&a.append(M(this._labels.would_have_paid,u(c,t),void 0,{bold:!0})),n?.accruing&&a.append(ar(this._labels.still_accruing)),a}_tooltipRowFor(e,t){let s=We(e),o=e.seriesId===H.saved.id?x(s,t):"",n=o==="loss"?this._labels.lost:e.seriesName;return nr(e.color,n,u(s,t),o?this._colour(wo[o]):void 0)}_bucketAt(e){if(e!==void 0)return(this._result?.series??[]).find(t=>t.start.getTime()===e)}_spanOf(e,t){return!e||!this._period?"":Lt(e.start,C(this._period),t)}_headerChip(e){let t=this._result?.totals?.actualCost;return Number.isFinite(t)&&!this._isEmpty()?u(t,e):""}_axisBounds(){if(!this._period)return{};let{start:e,end:t}=this._period,s=new Date(t.getTime()-1);return C(this._period)==="hour"?s.setMinutes(30,0,0):(s.getHours()===0&&s.setHours(s.getHours()-1),s.setHours(0,0,0,0)),{min:e.getTime(),max:s.getTime()}}_options(e){let t=this._labels;return{xAxis:{type:"time",...this._axisBounds()},grid:{top:15,bottom:0,left:1,right:1,containLabel:!0},yAxis:{type:"value",name:ce(e),nameGap:2,nameTextStyle:{align:"left"},boundaryGap:[0,0],splitNumber:5,splitLine:{show:!0},axisLabel:{formatter:s=>ie(s,e),hideOverlap:!0}},tooltip:{trigger:"axis",axisPointer:{type:"shadow"},formatter:s=>this._tooltipFor(s,e)},legend:{show:!0,type:"custom",data:[H.paid,H.saved,...this._result?.seriesBefore?.length?[Ae]:[]].map(s=>({id:s.id,name:t[s.name],itemStyle:{color:this._colour(s)}}))}}}},ir=(r,e,t=void 0)=>r.accruing?{value:e,itemStyle:{...t,opacity:ko}}:t?{value:e,itemStyle:t}:e,cr=(r,e,t)=>[r.start.getTime()+t,e,r.start.getTime()],lr=({id:r,name:e},t,s)=>({id:r,name:s[e],type:"bar",stack:"cost",barMaxWidth:yo,itemStyle:pr(t)}),pr=r=>({color:D(r,bo),borderColor:r,borderWidth:1}),Ke=class extends f{},Eo=()=>{b(hr,Ke),y(dr,ze,{name:"Home Energy Advisor: Cost over time",description:"What the period cost, stacked against what it would have cost at grid price."})};Eo();var he=(r,e)=>{let t=e?.statistics?.cost_savings;return!!(t&&r?.states?.[t])},mr=(r,e)=>({costSavings:r?.statistics?.cost_savings,batterySavings:r?.statistics?.battery_savings,lossesPaid:(e??[]).filter(t=>!t.untracked&&!t.upstream).filter(t=>!de(t)).map(t=>t.statistics?.actual_cost).filter(Boolean)}),_r=(r,e)=>{let t=e?.cost_sensors??{},s=[];for(let o of r?.energy_sources??[]){if(o?.type!=="grid")continue;let n=Array.isArray(o.flow_to)?o.flow_to:[o];for(let a of n){let c=a?.stat_compensation||a?.stat_energy_to&&t[a.stat_energy_to];c&&!s.includes(c)&&s.push(c)}}return s},fr=r=>[r.costSavings,r.batterySavings,...r.lossesPaid??[],...r.exportsEarned??[]].filter(Boolean),gr=(r,e,t)=>{let s=m=>So(r?.[m],t),o=s(e.costSavings),n=!!e.batterySavings,a=n?s(e.batterySavings):0,c=(e.lossesPaid??[]).reduce((m,_)=>m+s(_),0),i=e.exportsEarned??[],l=o-a,d=n?a-c:void 0,p=i.length?i.reduce((m,_)=>m+s(_),0):void 0;return{generationSaved:l,batterySaved:d,exportsEarned:p,total:l+(d??0)+(p??0)}},So=(r,{start:e,end:t})=>{if(!Array.isArray(r))return 0;let s=0;for(let o of r){let n=new Date(o.start).getTime();n<e.getTime()||n>=t.getTime()||typeof o.change=="number"&&(s+=o.change)}return s};var Xe="hea",vr="Home Energy Advisor",$o="mdi:home-lightning-bolt",yr=`ll-strategy-dashboard-${Xe}`,br=`ll-strategy-view-${Xe}`,$=4,wr=[{type:"custom:hea-totals-card"},{type:"custom:hea-devices-card",sort_by:"actual_cost"}],xr=[{type:"custom:hea-cost-over-time-card"},{type:"custom:hea-sources-card",sort_by:"energy_used"}],Ve=[{type:"custom:hea-device-costs-card"},{type:"custom:hea-distribution-card"},{type:"custom:hea-self-sufficiency-card"}],kr={type:"custom:hea-installation-card"},Ao=new Set(["custom:hea-sources-card","custom:hea-self-sufficiency-card"]),Oe=(r,e)=>e?r.filter(t=>!Ao.has(t.type)):r,Oo=r=>he(r,G(r))?[...Ve,kr]:Ve,To=r=>({...r,grid_options:{columns:"full",rows:"auto"}}),T=(r,e)=>({type:"grid",column_span:e,cards:r.map(To)}),Co=()=>({card:{type:"horizontal-stack",cards:[{type:"energy-date-selection",vertical_opening_direction:"up"},{type:"custom:hea-filter-card"}]},max_width:1600}),Er=r=>({type:"sections",max_columns:$,sections:[{type:"grid",cards:[{type:"markdown",content:E(r).no_devices}]}]}),Sr={type:"custom:hea-plans-card"},Fo=async r=>{try{let e=await r.callWS({type:"home_energy_advisor/list_plans"});return Array.isArray(e?.plans)&&e.plans.some(t=>!t.current)}catch{return!1}},$r=r=>({type:"sections",max_columns:$,sections:r.filter(e=>e.cards.length>0),footer:Co()}),Ro=(r,e)=>{if(w(r).length===0)return Er(r);let t=Q(r);return $r([T(wr,$),T(Oe(xr,t),$/2),T(Oe(Oo(r),t),$/2),...e?[T([Sr],$)]:[]])},[Io,Do]=wr,[No,Lo]=xr,[Mo,Go,Ho]=Ve,Ye=(r,{path:e,titleKey:t,icon:s},o)=>({...$r(o),path:e,title:E(r)[t],icon:s}),Po=(r,e)=>{if(w(r).length===0)return[Er(r)];let t=Q(r),s=he(r,G(r))?[kr]:[],o=[Ye(r,{path:"summary",titleKey:"tab_summary",icon:"mdi:view-dashboard"},[T([Io],$),T([No,...s],$/2),T(Oe([Go,Ho],t),$/2)]),Ye(r,{path:"devices",titleKey:"tab_devices",icon:"mdi:format-list-bulleted"},[T([Do],$),T([Mo],$/2),T(Oe([Lo],t),$/2)])];return e&&o.push(Ye(r,{path:"tariffs",titleKey:"tab_tariffs",icon:"mdi:cash-multiple"},[T([Sr],$)])),o},Ar=async r=>{let[,e]=await Promise.all([A(r),Fo(r)]);return e},qe=class extends HTMLElement{static async generate(e,t){return{views:Po(t,await Ar(t))}}static noEditor=!0;static getCreateSuggestions(){return{title:vr,icon:$o}}},Ze=class extends HTMLElement{static async generate(e,t){return Ro(t,await Ar(t))}},jo=r=>{globalThis.customStrategies=globalThis.customStrategies??[],globalThis.customStrategies.some(e=>e.type===r.type)||globalThis.customStrategies.push(r)},Bo=()=>{customElements.get(yr)||customElements.define(yr,qe),customElements.get(br)||customElements.define(br,Ze),jo({type:Xe,strategyType:"dashboard",name:vr,description:"What each device cost to run, and what solar and the battery saved."})};Bo();var Qe=Object.keys(S),Uo=Object.keys(L),Or=r=>{let e=new Map;for(let t of r){if(!t.upstream)continue;let s=e.get(t.upstream);s?s.push(t):e.set(t.upstream,[t])}return e},Je=(r,e)=>({...r,key:`${r.key}${Wo}`,name:`${r.name} ${e.device_untracked}`,upstream:r.key,untracked:!1,gross:!1,residualOf:r.key}),Wo="__untracked",Tr=(r,e)=>r.gross&&Qe.every(t=>!r[t])?[]:[Je(r,e)],zo=r=>{let e=Object.fromEntries(Qe.map(t=>[t,0]));for(let t of r)for(let s of Qe)e[s]+=t[s]??0;for(let t of Uo)e[t]=r.every(s=>typeof s[t]=="number")?r.reduce((s,o)=>s+o[t],0):void 0;return e.costSavings=e.costAtGridPrice-e.actualCost,e},Te=(r,e)=>{let t=Or(r);return t.size===0?r:r.flatMap(s=>t.has(s.key)?Tr(s,e):[s])},Cr=(r,e,t=s=>s)=>{let s=Or(r);if(s.size===0)return t(r).map(n=>({device:n,depth:0}));let o=(n,a)=>{if(!s.has(n.key))return[{device:n,depth:a}];let i=t([...s.get(n.key),...Tr(n,e)]).flatMap(d=>o(d,a+1)),l=i.filter(d=>!d.device.subtotal).map(d=>d.device);return[{device:{...n,...zo(l),subtotal:!0},depth:a},...i]};return t(r.filter(n=>!n.upstream)).flatMap(n=>o(n,0))};var R=Object.freeze(["#0072b2","#e69f00","#009e73","#cc79a7","#56b4e9","#d55e00","#8c6bb1","#3d9970"]),Ko=Object.freeze(["#4b46b3","#8d9b1f","#00a2ab","#b07ad2","#7fa0ee","#a8761b","#b26596","#5b8f3f"]),et=Object.freeze([R,Ko]),Xa=R.length*et.length,ee=Object.freeze({variable:"--secondary-text-color",fallback:"#8a8a8a"}),te=r=>{let e=(r??[]).filter(t=>!t.untracked).map(t=>t.key).sort(Yo);return new Map(e.map((t,s)=>{let o=Math.floor(s/R.length)%et.length;return[t,et[o][s%R.length]]}))},Yo=(r,e)=>r===e?0:r<e?-1:1;var Ce=(r,e,t)=>{let s=r<0?e.lost_share:e.saved_share;return h(s,{percent:Z(Math.abs(r),t)})},Vo=({costSavings:r,costAtGridPrice:e})=>{if(!(!Number.isFinite(r)||!Number.isFinite(e))&&!(e<=0))return r/e},ue=[{at:0,hue:3,light:48,dark:62},{at:.5,hue:35,light:46,dark:68},{at:1,hue:142,light:31,dark:76}],Fr={light:85,dark:70},qo=.7,Rr=(r,e,t)=>r+(e-r)*t,Zo=.6,Xo=(r,e)=>{let t=ue.findIndex(c=>r<=c.at);if(t<=0)return{hue:ue[0].hue,lightness:ue[0][e]};let s=ue[t-1],o=ue[t],n=(r-s.at)/(o.at-s.at),a=t===1?n:n**Zo;return{hue:Rr(s.hue,o.hue,a),lightness:Rr(s[e],o[e],n)}},Ir=.05,P=r=>Math.round(r*10)/10,tt=(r,{dark:e=!1,weight:t=1}={})=>{let s=e?"dark":"light",{hue:o,lightness:n}=Xo(Math.min(1,Math.max(0,r)),s),a=Fr[s]*t**qo;return{text:`hsl(${P(o)}, ${P(a)}%, ${P(n)}%)`,edge:`hsla(${P(o)}, ${P(Fr[s])}%, ${P(n)}%, ${P(t)})`}},Fe=(r,{dark:e=!1}={})=>{let t=o=>Math.max(0,o?.costAtGridPrice??0),s=Math.max(0,...(r??[]).map(t));return o=>{let n=Vo(o??{});if(n===void 0||s<=0)return;let a=Math.min(1,t(o)/s),c=a*(1+Ir)/(a+Ir);return{rate:n,...tt(n,{dark:e,weight:c})}}};var Pr="hea-device-costs-card",jr=`${Pr}-editor`,Dr={variable:"--error-color",fallback:"#db4437"},Qo={variable:"--secondary-text-color",fallback:"#727272"},Jo="earlier-period",en=["auto","vertical","horizontal"],tn="paid",rt="saved",Nr="before",rn=30,sn=46,on=64,nn=240,an=24,cn=12,ln=2,dn=10,hn=300,un=120,pn="40vw",mn={left:8,right:16,top:8,bottom:28,containLabel:!0},Lr=1.5,Mr=.8,Gr=.45,Hr=.22,_n=/:(?:paid|saved|before)$/,fn={gain:{variable:"--success-color",fallback:"#4caf50"},loss:{variable:"--error-color",fallback:"#db4437"}},gn=(r,e,t,s,o,n,a)=>{let c=document.createElement("div");if(c.append($e(e),M(s.paid,u(r.actualCost,t))),!a){let d=x(r.costSavings,t);c.append(M(r.costSavings<0?s.lost:s.saved,u(r.costSavings,t),d?o(d):void 0),M(s.would_have_paid,u(r.costAtGridPrice,t)));let p=yn(n,t,s);p&&c.append(p)}let i=bn(r,t,s,o);i&&c.append(i);let l=vn(r,t,s);return l&&c.append(l),c},yn=(r,e,t)=>{if(!r)return;let s=document.createElement("div");return s.style.marginTop="4px",s.style.color=r.text,s.textContent=Ce(r.rate,t,e),s},bn=(r,e,t,s)=>{let o=r.before?.actualCost;if(!Number.isFinite(o)||!Number.isFinite(r.actualCost))return;let n=r.actualCost-o,a=V("actualCost",n,e);return M(t.change,h(t.compared,{change:Y(n,e),before:u(o,e)}),a?s(a):void 0)},vn=({costFloor:r,costCeiling:e},t,s)=>{if(![r,e].every(n=>Number.isFinite(n)))return;let o=document.createElement("div");return o.style.marginTop="4px",o.style.opacity="0.75",o.textContent=h(s.range_device,{range:q([r,e],t)}),o},st=class extends F{static titleKey="title_device_costs";static narrowQuery=I;static getConfigElement(){return document.createElement(jr)}_isEmpty(){return this._ranked().every(e=>!e.costAtGridPrice&&!e.actualCost)}_caption(e){let t=super._caption(e);return this._isEmpty()?t:`${t}<div class="hint">${this._labels.device_costs_note}</div>`}_ranked(){return Te(this._result?.devices??[],this._labels).sort((e,t)=>t.actualCost-e.actualCost||e.name.localeCompare(t.name))}_colourFor(e){if(e.untracked)return this._colour(ee);let t=e.residualOf??e.key;return this._colours().get(t)??R[0]}_colours(){return te(w(this._hass))}_verdicts(){return Fe(this._ranked(),{dark:J(this)})}_sideways(){let e=this._config?.layout;return e==="horizontal"?!0:e==="vertical"?!1:this._isNarrow()}_comparing(){return this._ranked().some(e=>e.before)}_series(){let e=this._sideways()?this._sidewaysSeries():this._standingSeries();return fe(this._result?.gridOnly?e.filter(({id:t})=>t!==rt&&!t.endsWith(`:${rt}`)):e)}_sidewaysSeries(){let e=this._ranked(),t=this._colour(Dr),s=this._labels,o=n=>this._colourFor(n);return[{id:tn,name:s.paid,type:"bar",stack:"cost",data:e.map(n=>({value:n.actualCost,itemStyle:{color:D(o(n),Mr)}}))},{id:rt,name:s.saved,type:"bar",stack:"cost",data:e.map(n=>{let a=n.costSavings<0?t:o(n);return{value:n.costSavings,itemStyle:{color:D(a,Hr),borderColor:a,borderWidth:Lr}}})},...this._comparing()?[{id:Nr,name:s.compared_series,type:"bar",stack:"earlier",data:e.map(n=>({value:n.before?n.before.actualCost:null,itemStyle:{color:D(o(n),Gr)}}))}]:[]]}_standingSeries(){let e=this._colour(Dr);return this._ranked().flatMap(t=>{let s=this._colourFor(t),o=t.costSavings<0?e:s,n=t.name;return[{id:`${t.key}:paid`,name:n,type:"bar",stack:t.key,itemStyle:{color:D(s,Mr)},data:[t.actualCost]},{id:`${t.key}:saved`,name:n,type:"bar",stack:t.key,itemStyle:{color:D(o,Hr),borderColor:o,borderWidth:Lr},data:[t.costSavings]},...t.before?[{id:`${t.key}:before`,name:n,type:"bar",stack:`${t.key}:before`,itemStyle:{color:D(s,Gr)},data:[t.before.actualCost]}]:[]]})}_tooltipFor({seriesId:e,dataIndex:t},s){let o=this._ranked(),n=this._sideways()?o[t]:o.find(a=>a.key===String(e??"").replace(_n,""));return n?gn(n,n.name,s,this._labels,a=>this._colour(fn[a]),this._verdicts()(n),this._result?.gridOnly):void 0}_earlierKey(){if(!this._comparing())return[];let e=this._labels.compared_series,t={color:this._colour(Qo)};return this._sideways()?[{id:Nr,name:e,itemStyle:t}]:[{id:Jo,secondaryIds:this._ranked().filter(s=>s.before).map(s=>`${s.key}:before`),name:e,itemStyle:t}]}_chartHeight(){if(this._sideways()){let t=this._ranked().length,s=this._comparing()?sn:rn;return`${Math.max(nn,on+t*s)}px`}let e=hn+this._legendHeight();return`clamp(${e}px, ${pn}, ${e+un}px)`}_legendHeight(){let e=Math.min(this._ranked().length,dn)+this._earlierKey().length;return Math.ceil(e/ln)*an+cn}_options(e){return this._sideways()?this._sidewaysOptions(e):this._standingOptions(e)}_sidewaysOptions(e){let t=this._earlierKey();return{xAxis:{type:"value",name:ce(e),axisLabel:{formatter:s=>ie(s,e),hideOverlap:!0}},yAxis:{type:"category",data:this._ranked().map(s=>s.name),inverse:!0},grid:mn,tooltip:{trigger:"item",formatter:s=>this._tooltipFor(s,e)},...t.length?{legend:{show:!0,type:"custom",data:t}}:{}}}_standingOptions(e){return{xAxis:{type:"category",data:[le(this._period,e)]},yAxis:{type:"value",name:ce(e),nameGap:2,nameTextStyle:{align:"left"},axisLabel:{formatter:t=>ie(t,e),hideOverlap:!0}},tooltip:{trigger:"item",formatter:t=>this._tooltipFor(t,e)},legend:{show:!0,type:"custom",data:[...this._ranked().map(t=>({id:`${t.key}:paid`,secondaryIds:[`${t.key}:saved`,...t.before?[`${t.key}:before`]:[]],name:t.name,itemStyle:{color:this._colourFor(t)}})),...this._earlierKey()]}}}},ot=class extends f{_extraSchema(){return[{name:"layout",selector:{select:{mode:"dropdown",options:en}}}]}},wn=()=>{b(jr,ot),y(Pr,st,{name:"Home Energy Advisor: Device costs (chart)",description:"What each device cost over the selected period, dearest first."})};wn();var at=`${Ee}
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
`,xn=(r,e,t,s)=>(r==="costSavings"?x(t,s):V(e,t,s))??"",nt=({classes:r=[],styles:e=[]})=>{let t=r.filter(Boolean),s=e.filter(Boolean);return(t.length?` class="${t.join(" ")}"`:"")+(s.length?` style="${s.join("; ")}"`:"")},Br=r=>r?`box-shadow: inset ${kn} 0 0 ${r.edge}`:"",kn="4px",j=class extends O{static columns=[];static sorts={};static defaultSort="";static cardStyle=at;setConfig(e){let{sorts:t}=this.constructor;if(e.sort_by!==void 0&&!(e.sort_by in t))throw new Error(`\`sort_by\` must be one of: ${Object.keys(t).join(", ")}`);super.setConfig(e)}getCardSize(){return 3+Math.ceil((this._result?.devices.length??3)/2)}_columns(){return this.constructor.columns}_body(e){let t=this._columns(),s=this._verdictScale();return`
      <div class="scroll">
        <table>
          <thead><tr>${t.map(o=>this._heading(o,e)).join("")}</tr></thead>
          <tbody>${this._ranked().map(({device:o,depth:n})=>this._row(o,e,s,n)).join("")}</tbody>
          <tfoot>${this._total(e,s)}</tfoot>
        </table>
      </div>`}_verdictScale(){if(this._columns().some(e=>e.carriesVerdict))return Fe(this._result?.devices??[],{dark:J(this)})}_heading({label:e},t){let s=this._labels;if(typeof e!="function")return`<th>${Se(e)}${s[e]}</th>`;let{text:o,unit:n}=e(t,s);return`<th>${o} <span class="unit">${k(n)}</span></th>`}_rank(e){let{sorts:t,defaultSort:s}=this.constructor,{field:o}=t[this._config?.sort_by??s];return[...e].sort((n,a)=>a[o]-n[o]||n.name.localeCompare(a.name))}_ranked(){return Cr(this._result?.devices??[],this._labels,e=>this._rank(e))}_row(e,t,s,o){return`<tr${e.subtotal?' class="subtotal"':""}>${this._columns().map(a=>this._cell(a,e,t,s?.(e),o)).join("")}</tr>`}_cell(e,t,s,o,n){let{field:a,derive:c,format:i,reveal:l}=e;if(!i)return`<th scope="row"${nt({classes:[n?"inside":""],styles:[n?`--depth: ${n}`:"",Br(o)]})}>${k(t.name)}</th>`;let d=c?c(t):t[a],p=this._revealed(i(d,s),l?.(t,s,this._labels));return`<td${this._figureAttributes(e,d,o,s)}>${p}</td>`}_figureAttributes({field:e,tone:t,muted:s,carriesVerdict:o},n,a,c){let i=o?this._verdictOn(a,c):null;return nt({classes:[xn(e,t,n,c),s?"muted":""],styles:[i?.style]})+(i?` title="${k(i.title)}"`:"")}_revealed(e,t){return t?`<span class="reveal" tabindex="0" aria-label="${k(t.label)}">${e}<span class="revealed" aria-hidden="true">${k(t.text)}</span></span>`:e}_total(e,t){let s=this._sumOfShown(),o=t?.(s);return`<tr>${this._columns().map(a=>{let{field:c,derive:i,format:l}=a;if(!l)return`<th scope="row"${nt({styles:[Br(o)]})}>${this._labels.total}</th>`;let d=i?i(s):s[c];return`<td${this._figureAttributes(a,d,o,e)}>${l(d,e)}</td>`}).join("")}</tr>`}_verdictOn(e,t){return e?{style:`color: ${e.text}`,title:Ce(e.rate,this._labels,t)}:null}_sumOfShown(){let e=[...new Set(this._columns().flatMap(({field:a,fields:c,derive:i,format:l})=>l?i?c??[]:a?[a]:[]:[]))],t=Te(this._result?.devices??[],this._labels),s=Object.fromEntries(this._columns().flatMap(({fields:a,field:c,readField:i})=>i?(a??[c]).map(l=>[l,i]):[])),o=a=>t.reduce((c,i)=>{for(let l of e){let d=a(i);c[l]+=s[l]?s[l](d,l):d[l]}return c},Object.fromEntries(e.map(c=>[c,0]))),n=o(a=>a);return t.length>0&&t.every(a=>a.before)&&(n.before=o(a=>a.before)),n}},Re=(r,e)=>[{name:"sort_by",selector:{select:{mode:"dropdown",options:Object.entries(r).map(([t,{label:s}])=>({value:t,label:e[s]}))}}}];var Wr="hea-devices-card",zr=`${Wr}-editor`,En=({actualCost:r,energyUsed:e})=>e>0?r/e:void 0,Kr=r=>Object.values(L).every(e=>e in(r.statistics??{})),Yr=r=>({field:r,fields:[r],derive:e=>!e.statistics||de(e)?e[r]:void 0}),Vr={...Yr("costAtGridPrice"),label:"would_have_paid",format:u,muted:!0},qr={...Yr("costSavings"),label:"saved",format:u},pe={fields:["costFloor","costCeiling"],derive:({costFloor:r,costCeiling:e})=>[r,e],label:"range_column",format:q,readField:(r,e)=>Number.isFinite(r[e])?r[e]:r.actualCost},Zr={fields:["actualCost"],derive:({actualCost:r,before:e})=>e&&Number.isFinite(r)&&Number.isFinite(e.actualCost)?r-e.actualCost:void 0,label:"change",format:Y,tone:"actualCost"},Ie={field:"actualCost",label:"paid",format:u,carriesVerdict:!0,reveal:(r,e)=>{if(!Kr(r)||!pe.fields.every(s=>Number.isFinite(r[s])))return null;let t=q(pe.derive(r),e);return{text:t,label:`${u(r.actualCost,e)} (${t})`}}},Xr={field:"forgoneExport",label:"forgone_column",format:u,muted:!0},Ur=[{field:"name",label:"device"},{field:"energyUsed",label:"energy",format:v},Ie,Zr,pe,Vr,qr,Xr,{derive:En,label:(r,e)=>({text:e.rate,unit:xe(r)}),format:ke}],Qr={actual_cost:{field:"actualCost",label:"paid"},cost_at_grid_price:{field:"costAtGridPrice",label:"would_have_paid"},cost_savings:{field:"costSavings",label:"saved"},energy_used:{field:"energyUsed",label:"energy_used"}},it=class extends j{static titleKey="title_devices";static columns=Ur;static sorts=Qr;static defaultSort="actual_cost";static narrowQuery=I;static cardStyle=`${j.cardStyle}
    .disclosure {
      margin-top: var(--hea-space-m);
      color: var(--secondary-text-color);
      font-size: 0.8em;
    }
  `;static getConfigElement(){return document.createElement(zr)}_columns(){let e=this._rangeAsColumn(),t=new Set;e||t.add(pe),this._showsForgone()||t.add(Xr),this._hasComparison()||t.add(Zr);let s=!!this._result?.gridOnly;return s&&(t.add(Vr),t.add(qr)),Ur.filter(o=>!t.has(o)).map(o=>{if(o!==Ie)return o;let n=e?{...Ie,reveal:void 0}:Ie;return s?{...n,carriesVerdict:!1}:n})}_rangeAsColumn(){let e=this._config?.range;return(e==="column"||e!=="rollover"&&!this._isNarrow())&&this._hasEveryBound()}_showsForgone(){return this._hasForgone()&&!this._isNarrow()}_hasComparison(){return(this._result?.devices??[]).some(e=>e.before)}_hasForgone(){return(this._result?.devices??[]).some(e=>(e.forgoneExport??0)>0)}_hasEveryBound(){let e=(this._result?.devices??[]).filter(Kr);return e.length>0&&e.every(t=>pe.fields.every(s=>Number.isFinite(t[s])))}_body(e){return`${super._body(e)}${this._disclosure(e)}`}_disclosure(e){let t=[this._rangeDisclosure(e),this._forgoneNote()].filter(Boolean);return t.length?`<div class="disclosure">${t.join(" ")}</div>`:""}_forgoneNote(){return this._hasForgone()?this._showsForgone()?this._labels.forgone_note:this._labels.forgone_hidden_note:""}_rangeDisclosure(e){if(this._hasEveryBound())return this._rangeNote();let t=this._result?.wholeHome;if(!t)return"";let s=q([t.costFloor,t.costCeiling],e);return h(this._labels.range_whole_home,{range:s})}_rangeNote(){return this._rangeAsColumn()?this._labels.range_note:this._labels.range_note_rollover}},ct=class extends f{_extraSchema(){let e=E(this._hass);return[...Re(Qr,e),{name:"range",selector:{select:{mode:"dropdown",options:[{value:"auto",label:e.editor_range_auto},{value:"rollover",label:e.editor_range_rollover},{value:"column",label:e.editor_range_column}]}}}]}},Sn=()=>{b(zr,ct),y(Wr,it,{name:"Home Energy Advisor: Devices",description:"Every tracked device over the selected period, ordered by what it cost."})};Sn();var me="household",re=Object.freeze({source:0,household:1,floor:2,area:3,device:4}),Jr=Object.freeze({cost:{field:"actualCost",sources:null},energy:{field:"energyUsed",sources:[{id:"grid",field:"energyFromGrid",variable:"--energy-grid-consumption-color",fallback:"#488fc2"},{id:"generation",field:"energyFromGeneration",variable:"--energy-solar-color",fallback:"#ff9800"},{id:"battery",field:"energyFromBattery",variable:"--energy-battery-out-color",fallback:"#4db6ac"}]}}),$n=r=>{let e=te(r);return t=>t.untracked?ee.fallback:e.get(t.key)??R[0]},An=({fallback:r})=>r,ss=(r,e,{metric:t="cost",colour:s=An,deviceColour:o=$n(r),groupByFloor:n=!0,groupByArea:a=!0}={})=>{let{field:c,sources:i}=Jr[t]??Jr.cost,l=On(r,c).filter(g=>g.value>0);if(l.length===0)return{nodes:[],links:[]};let d=l.reduce((g,oe)=>g+oe.value,0),p=Cn(l,{groupByFloor:n,groupByArea:a}),m=Fn(l,e,o),_=Rn(i,r.filter(g=>g[c]>0),e,s);return{nodes:[..._,{id:me,label:e.household,value:d,index:re.household},...p.nodes,...m.nodes],links:[..._.map(g=>({source:g.id,target:me,value:g.value})),...p.links,...m.links]}},On=(r,e)=>{let t=new Map(r.map(a=>[a.key,a])),s=new Map,o=[];for(let a of r){let c=Tn(a,t);c?s.has(c.key)?s.get(c.key).push(a):s.set(c.key,[a]):o.push(a)}let n=a=>{let c=Math.max(a[e]??0,0),i=(s.get(a.key)??[]).map(n).filter(l=>l.value>0);return{device:a,own:c,inside:i,value:i.reduce((l,d)=>l+d.value,c)}};return o.map(n)},Tn=(r,e)=>{let t=e.get(r.upstream);if(!t)return null;let s=new Set;for(let o=t;o;o=e.get(o.upstream)){if(o.key===r.key)return null;if(s.has(o.key))break;s.add(o.key)}return t},Cn=(r,{groupByFloor:e,groupByArea:t})=>{let s=new Map,o=new Map,n=[];return r.forEach(({device:a,value:c})=>{let i=e&&a.floorId?es(s,a.floorId,a.floorName):null,l=t&&a.areaId?es(o,a.areaId,a.areaName):null;i&&(i.value+=c),l&&(l.value+=c,l.floorId??=i?.id??null),n.push({source:In(l,i),target:B(a),value:c})}),{nodes:[...rs(s,"floor_",re.floor),...rs(o,"area_",re.area)],links:[...Dn(s,o),...n]}},Fn=(r,e,t)=>{let s=re.device+os(r),o=[],n=[],a=(c,i)=>{let{device:l,own:d,inside:p,value:m}=c,_=p.length>0;if(o.push({id:B(l),label:l.name,value:m,index:_?re.device+i:s,color:t(l),...ts(l)}),!!_&&(p.forEach(g=>{n.push({source:B(l),target:B(g.device),value:g.value}),a(g,i+1)}),d>0)){let g=Je(l,e);o.push({id:B(g),label:g.name,value:d,index:s,color:t(l),...ts(l)}),n.push({source:B(l),target:B(g),value:d})}};return r.forEach(c=>a(c,0)),{nodes:o,links:n}},os=r=>r.reduce((e,t)=>t.inside.length>0?Math.max(e,1+os(t.inside)):e,0),B=r=>`device_${r.key}`,Rn=(r,e,t,s)=>(r??[]).map(o=>({id:`source_${o.id}`,label:t[o.id],value:e.reduce((n,a)=>n+(a[o.field]??0),0),index:re.source,color:s(o)})).filter(o=>o.value>0),es=(r,e,t)=>(r.has(e)||r.set(e,{id:e,name:t||e,value:0}),r.get(e)),In=(r,e)=>r?`area_${r.id}`:e?`floor_${e.id}`:me,ts=r=>{let e=r.statistics?.actual_cost;return e?{entityId:e}:{}},rs=(r,e,t)=>[...r.values()].map(s=>({id:`${e}${s.id}`,label:s.name,value:s.value,index:t})),Dn=(r,e)=>[...[...r.values()].map(t=>({source:me,target:`floor_${t.id}`,value:t.value})),...[...e.values()].map(t=>({source:t.floorId?`floor_${t.floorId}`:me,target:`area_${t.id}`,value:t.value}))];var ns="hea-distribution-card",as=`${ns}-editor`,_e={cost:{titleKey:"title_distribution",emptyKey:"no_cost_in_period",format:u},energy:{titleKey:"title_distribution_energy",emptyKey:"no_energy_in_period",format:v}},Nn="400px",Ln=88,Mn=240,Gn=["auto","horizontal","vertical"],lt=Object.freeze({group_by_floor:!0,group_by_area:!0}),dt=class extends F{static titleKey="title_distribution";static chartTag="ha-sankey-chart";static bearingCard={type:"energy-sankey"};static narrowQuery=I;static cardStyle=`
    ha-sankey-chart { display: block; min-height: 240px; }
  `;static getConfigElement(){return document.createElement(as)}_isEmpty(){return this._layout().nodes.length===0}_verticalHeight({nodes:e}){let t=new Set(e.map(s=>s.index)).size;return`${Math.max(Mn,t*Ln)}px`}_metric(){return _e[this._config?.metric]?this._config.metric:"cost"}_titleKey(){return _e[this._metric()].titleKey}_emptyKey(){return _e[this._metric()].emptyKey}_layout(){let e=te(w(this._hass));return ss(this._result?.devices??[],this._labels,{metric:this._metric(),groupByFloor:this._config?.group_by_floor??lt.group_by_floor,groupByArea:this._config?.group_by_area??lt.group_by_area,colour:t=>this._colour(t),deviceColour:t=>t.untracked?this._colour(ee):e.get(t.key)??R[0]})}_chartMarkup(){return"<ha-sankey-chart></ha-sankey-chart>"}_draw(e){e.data=this._layout(),e.vertical=this._isVertical(),e.style.height=this._isVertical()?this._verticalHeight(e.data):Nn;let t=this._chartLocale(),{format:s}=_e[this._metric()];e.valueFormatter=o=>s(o,t),this.toggleAttribute("data-vertical",e.vertical)}_isVertical(){let e=this._config?.layout;return e==="vertical"?!0:e==="horizontal"?!1:this._isNarrow()}},ht=class extends f{_extraSchema(){return[{name:"metric",selector:{select:{mode:"dropdown",options:Object.keys(_e)}}},{name:"layout",selector:{select:{mode:"dropdown",options:Gn}}},{name:"group_by_floor",selector:{boolean:{}}},{name:"group_by_area",selector:{boolean:{}}}]}setConfig(e){super.setConfig({...lt,...e})}},Hn=()=>{b(as,ht),y(ns,dt,{name:"Home Energy Advisor: Cost distribution",description:"Where the period's cost went, by floor, room, circuit and device."})};Hn();var is="hea-filter-card",cs=`${is}-editor`,Pn=[{kind:"area",label:"filter_rooms",id:"areaId",name:"areaName"},{kind:"floor",label:"filter_floors",id:"floorId",name:"floorName"}],U=({kind:r,id:e})=>`${r}:${e??""}`,jn=r=>{let[e,t]=[r.slice(0,r.indexOf(":")),r.slice(r.indexOf(":")+1)];return{kind:e,id:t===""?null:t}},ut=class extends HTMLElement{constructor(){super(),this.attachShadow({mode:"open"})}setConfig(e){this._config=e,this._render()}set hass(e){this._hass=e,A(e).then(()=>this._renderIfChanged()),this._renderIfChanged()}getCardSize(){return 1}static getConfigElement(){return document.createElement(cs)}connectedCallback(){this._render(),this._unfilter??=be(this._config?.collection_key,()=>this._renderIfChanged())}_signature(){return JSON.stringify([this._allDevices().map(e=>[e.key,e.name,e.areaId,e.areaName,e.floorId,e.floorName,e.labels]),U(ne(this._config?.collection_key)),this._labels.filter_rooms])}_renderIfChanged(){this._signature()!==this._drawn&&this._render()}disconnectedCallback(){this._unfilter?.(),this._unfilter=null}get _labels(){return E(this._hass)}_devices(){return w(this._hass).filter(e=>!e.untracked)}_allDevices(){return w(this._hass)}_optionsFor({kind:e,id:t,name:s},o){let n=new Map,a=!1;for(let i of o)i[t]?n.set(i[t],i[s]??i[t]):a=!0;let c=[...n.entries()].map(([i,l])=>({value:U({kind:e,id:i}),text:l})).sort((i,l)=>i.text.localeCompare(l.text));return a&&c.push({value:U({kind:e,id:null}),text:this._labels.filter_unfiled}),c}_labelOptions(e){let t=Ct(this._hass);return[...new Set(e.flatMap(o=>o.labels??[]))].map(o=>({value:U({kind:"label",id:o}),text:t[o]??o})).sort((o,n)=>o.text.localeCompare(n.text))}_deviceOptions(){return this._allDevices().map(e=>({value:U({kind:"device",id:e.key}),text:e.name})).sort((e,t)=>e.text.localeCompare(t.text))}_groups(){let e=this._devices(),t=Pn.map(o=>({label:this._labels[o.label],options:this._optionsFor(o,e)})),s=this._labelOptions(e);return s.length&&t.push({label:this._labels.filter_labels,options:s}),t.push({label:this._labels.filter_devices,options:this._deviceOptions()}),t.filter(o=>o.options.length>0)}_render(){let e=this._labels,t=this._devices();this._drawn=this._signature();let s=t.length?this._control(e):`<p class="message">${e.no_devices}</p>`;this.shadowRoot.innerHTML=`
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
    `;let o=this.shadowRoot.querySelector("select");o&&(o.value=U(ne(this._config?.collection_key)),o.addEventListener("change",()=>It(this._config?.collection_key,jn(o.value))))}_control(e){let t=this._groups().map(s=>`<optgroup label="${k(s.label)}">${s.options.map(o=>`<option value="${k(o.value)}">${k(o.text)}</option>`).join("")}</optgroup>`).join("");return`<div class="body">
      <span class="label">${e.title_filter}</span>
      <select>
        <option value="${U({kind:"all",id:null})}">${k(e.filter_everything)}</option>
        ${t}
      </select>
    </div>`}},pt=class extends f{},Bn=()=>{b(cs,pt),y(is,ut,{name:"Home Energy Advisor: Filter",description:"Narrow every Home Energy Advisor card on the page to a room, a floor, a label or one device."})};Bn();var ls="hea-installation-card",ds=`${ls}-editor`,Un=[{key:"generationSaved",label:"generation_saved"},{key:"batterySaved",label:"battery_saved"},{key:"exportsEarned",label:"exports_earned"}],mt=class extends O{static titleKey="title_installation";static cardStyle=`
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
  `;static getConfigElement(){return document.createElement(ds)}getCardSize(){return 4}async _fetch(){if(!this._hass||!this._period)return;let e=++this._request;await A(this._hass);let t=G(this._hass);if(!he(this._hass,t)){this._state="empty",this._render();return}try{let s={...mr(t,w(this._hass)),exportsEarned:await this._exportStatistics()},o=await this._hass.callWS({type:"recorder/statistics_during_period",start_time:this._period.start.toISOString(),end_time:this._period.end.toISOString(),statistic_ids:fr(s),period:C(this._period),types:["change"]});if(e!==this._request)return;this._earned=gr(o,s,this._period),this._state="ready"}catch(s){if(e!==this._request)return;this._state="error",console.error(`${this.localName}: could not load statistics`,s)}this._render()}async _exportStatistics(){try{let[e,t]=await Promise.all([this._hass.callWS({type:"energy/get_prefs"}),this._hass.callWS({type:"energy/info"})]);return _r(e,t)}catch{return[]}}_content(e){return this._state==="empty"?`<p class="message">${this._labels.no_installation}</p>`:super._content(e)}_body(e){let t=this._earned;return`
      <div class="parts">
        ${Un.filter(({key:o})=>t?.[o]!==void 0).map(({key:o,label:n})=>this._line("part",o,this._labels[n],e)).join("")}
        ${this._line("total","total",this._labels.total,e)}
      </div>
      <div class="hint">${this._labels.installation_note}</div>`}_line(e,t,s,o){let n=this._earned?.[t],a=x(n,o);return`
      <div class="${e}">
        <span class="label">${s}</span>
        <span class="value${a?` ${a}`:""}" data-figure="${t}">${u(n,o)}</span>
      </div>`}},_t=class extends f{},Wn=()=>{b(ds,_t),y(ls,mt,{name:"Home Energy Advisor: What your installation earned",description:"What your generation, battery and exports earned over the selected period, for the whole home."})};Wn();var ms="hea-plans-card",_s=`${ms}-editor`,zn="home_energy_advisor/compare_plans",Kn=[{key:"energy",label:"plans_energy",group:"pay"},{key:"daily",label:"plans_daily",figure:"daily_charges",group:"pay"},{key:"demand",label:"plans_demand",figure:"demand_charges",group:"pay"},{key:"export",label:"plans_export",figure:"export_credit",group:"earn"}],Yn=[{key:"pay",label:"plans_you_pay"},{key:"earn",label:"plans_you_earn"}],Vn=r=>"demand_charges"in r||!!r.demand_charge_missing,z=r=>!!(r.incomplete||r.no_price),qn=r=>!r.follows_prices&&!!(r.rates?.import_market||r.rates?.export_market),hs="grid",Zn=(r,e)=>z(r)||z(e)?(z(r)?1:0)-(z(e)?1:0):r.total-e.total,gt=class extends O{static titleKey="title_plans";static narrowQuery=I;static cardStyle=`${at}
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
    /* On a phone a total in credit and the difference may break before their
       word, "in credit" or "cheaper" under the figure, so the last column fits
       the screen rather than running off it (HEA-314). */
    @media (max-width: 767px) {
      .plans td.total, .plans td.difference, .plans thead th:last-child {
        white-space: normal;
        min-width: 4.5em;
      }
    }
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
  `;static getConfigElement(){return document.createElement(_s)}getCardSize(){return 5}async _fetch(){if(!this._hass||!this._period)return;let e=++this._request;await A(this._hass);try{let t=await this._hass.callWS({type:zn,start_time:this._period.start.toISOString(),end_time:this._period.end.toISOString()});if(e!==this._request)return;this._compared=t,this._state=t?.plans?.length?"ready":"empty"}catch(t){if(e!==this._request)return;this._state="error",console.error(`${this.localName}: could not compare the plans`,t)}this._render()}_content(e){return this._state==="empty"?`<p class="message">${this._labels.no_plans}</p>`:super._content(e)}_body(e){if(!this._compared?.plans)return"";let t=[...this._compared.plans].sort(Zn),s=t.filter(_=>!z(_)),o=s.find(_=>_.current),n=o?.daily_charge_missing?void 0:o,a=s.length>1?s[0]:void 0,c=!this._isNarrow();this._gridOnly=Q(this._hass);let i=t.some(Vn),l=c?Kn.filter(_=>(!this._gridOnly||_.group!=="earn")&&(i||_.key!=="demand")):[],d=c&&t.some(_=>"without_installation"in _),p=[this._compared.hours===0?this._labels.plans_no_readings:"",this._currentNote(o),o?.history_from?.length?h(this._labels.plans_current_history_from,{plans:N(new Intl.ListFormat(e.language,{type:"conjunction"}).format(o.history_from))}):"",this._labels.plans_note,this._archivedNote(),s.some(_=>_.breakdown)?this._labels.plans_open:"",c?"":this._breakdownHidden(i),s.some(qn)?this._resolution(e):"",d&&i?this._labels.plans_demand_note:""].filter(Boolean),m={current:n,cheapest:a,parts:l,without:d};return`
      ${this._flows(e)}
      ${this._leftOut(e)}
      <div class="scroll">
        <table class="plans">
          <thead>${this._head(m)}</thead>
          ${t.map(_=>this._plan(_,m,e)).join("")}
        </table>
      </div>
      ${p.map(us).join("")}`}_head({parts:e,without:t}){let s=(i,l="")=>`<th${se(l)}>${i}</th>`,o=[s(this._labels.plans_total,"rule"),...t?[s(this._labels.plans_without,"rule without")]:[],s(this._labels.plans_vs_current)],n=[s(this._labels.plans_plan),...e.map((i,l)=>s(this._labels[i.label],this._partClasses(e,l))),...o].join("");if(!e.length)return`<tr>${n}</tr>`;let a=Yn.map(i=>{let l=e.filter(p=>p.group===i.key).length;return l?`<th class="${i.key==="earn"?"rule earn":"rule"}" colspan="${l}">${this._labels[i.label]}</th>`:""}).join(""),c=t?`<th class="rule"></th><th class="rule without">${this._labels.plans_without_group}</th><th></th>`:`<th colspan="${o.length}" class="rule"></th>`;return`<tr class="groups"><th></th>${a}${c}</tr>
      <tr>${n}</tr>`}_without(e,t){if(!("without_installation"in e))return'<td class="rule"></td>';let s=u(e.without_installation,t),o=x(e.without_installation,t)?"loss":"",n=e.without_installation-e.total,a=u(Math.abs(n),t),c=x(n,t),i=c==="loss"?h(this._labels.plans_costs_more,{amount:a}):h(this._labels.plans_saves,{amount:a}),l=["saves",c].filter(Boolean).join(" ");return`<td class="${["rule",o].filter(Boolean).join(" ")}" data-figure="without:${e.id}">${s}<div class="${l}">${i}</div></td>`}_partClasses(e,t){let s=e[t];return[t===0||e[t-1].group!==s.group?"rule":"",s.group==="earn"?"earn":""].filter(Boolean).join(" ")}_currentNote(e){return e?e.daily_charge_missing?this._labels.plans_current_daily_missing:"":this._labels.plans_no_current}_breakdownHidden(e){let t=this._gridOnly?"plans_breakdown_hidden_import":"plans_breakdown_hidden";return this._labels[e?`${t}_demand`:t]}_flows(e){if(!this._compared.hours)return"";let t=this._gridOnly?"plans_flows_import":"plans_flows",s=this._compared.left_out?.length?`${t}_compared`:t,o=this._labels[s];return`<div class="flows">${h(o,{imported:v(this._compared.imported_kwh,e),exported:v(this._compared.exported_kwh,e)})}</div>`}_leftOut(e){let t=this._compared.left_out??[];if(!t.length||!this._compared.hours)return"";let s=new Map;for(let n of t){let a=n.kwh!==void 0,c=`${a?"impossible":"missing"}:${n.source}`,i=s.get(c)??{source:n.source,impossible:a,whens:[]};i.whens.push(this._stretch(n,e)),s.set(c,i)}let o=new Map;for(let{source:n,impossible:a,whens:c}of s.values()){let i=c.join(", "),l=a?`impossible:${n}`:`missing:${i}`,d=o.get(l)??{when:i,impossible:a,sources:[]};d.sources.push(n),o.set(l,d)}return[...o.values()].map(n=>`<div class="flows left-out" data-source="${N(n.sources.join(" "))}">${this._leftOutWording(n,e)}</div>`).join("")}_leftOutWording({when:e,impossible:t,sources:s},o){if(t)return h(this._labels.plans_left_out_impossible,{when:e,sensor:this._sensor(s[0])});if(s.length>1){let n=s.map(i=>i===hs?this._labels.plans_your_grid_meters:this._sensor(i)),a=this._labels.plans_left_out_many,c=new Intl.ListFormat(o,{type:"conjunction"}).format(n);return/(^|[.!?]\s+)\{sources\}/.test(a)&&(c=c.charAt(0).toLocaleUpperCase(o)+c.slice(1)),h(a,{when:e,sources:c})}return s[0]===hs?h(this._labels.plans_left_out_meters,{when:e}):h(this._labels.plans_left_out_price,{when:e,sensor:this._sensor(s[0])})}_stretch(e,t){let s=new Date(e.from),o=new Date(e.to),n=ve(s,t)===ve(o,t),a={from:we(s,t),to:n?ae(o,t):we(o,t)};return e.kwh===void 0?h(this._labels.plans_stretch,a):h(this._labels.plans_stretch_kwh,{...a,kwh:v(e.kwh,t)})}_sensor(e){let t=this._hass?.states?.[e]?.attributes?.friendly_name,s=N(e);return t&&t!==e?`${N(t)} (${s})`:s}_plan(e,{current:t,cheapest:s,parts:o,without:n},a){let c=this._opened.has(e.id),i=this._name(e,s,c,a),l=1+o.length+2+(n?1:0);if(z(e)){let g=e.follows_prices?"plans_no_price_current":"plans_no_price",oe=e.no_price?h(this._labels[g],{sensors:(e.no_price_entities??[]).map($s=>this._sensor($s)).join(", ")}):this._labels.plans_incomplete;return`<tbody data-plan="${e.id}"><tr>${i}
        <td class="incomplete rule" colspan="${l-1}">${oe}</td></tr></tbody>`}let d=o.map((g,oe)=>this._part(e,g,a,this._partClasses(o,oe))).join(""),p=t&&e!==t?this._difference(e,t,a):"<td></td>",m=this._exportNotes(e,a).trim(),_=c&&e.breakdown?`<tr class="bill-row"><td colspan="${l}">${this._bill(e,a)}</td></tr>`:"";return`<tbody data-plan="${e.id}">
      <tr class="figures">${i}${d}${this._total(e,a)}${n?this._without(e,a):""}${p}</tr>
      ${m?`<tr class="note"><td colspan="${l}">${m}</td></tr>`:""}
      ${_}
    </tbody>`}_name(e,t,s,o){let n=this._beenOn(e,o),a=[e.current?["current",this._labels.plans_your_plan]:void 0,n?["been-on",n]:void 0,e===t?["cheapest",this._labels.plans_cheapest]:void 0].filter(Boolean).map(([i,l])=>`<span class="tag ${i}">${l}</span>`).join("");return`<th>${e.breakdown&&!z(e)?`<button class="open" type="button" aria-expanded="${s}">${N(e.name)}</button>`:N(e.name)}${ea(a)}</th>`}_beenOn(e,t){let s=e.been_on??[];if(!s.length)return"";let o=Xn(t),n=l=>N(Qn(l,t)),a=s.find(l=>(!l.from||l.from<=o)&&(!l.until||l.until>=o));if(a)return a.from?h(this._labels.plans_since,{date:n(a.from)}):this._labels.plans_on_now;let c=s.filter(l=>l.from&&l.from>o).map(l=>l.from).sort()[0];if(c)return h(this._labels.plans_from,{date:n(c)});let i=s.map(l=>l.until).filter(Boolean).sort().at(-1);return i?h(this._labels.plans_until,{date:n(i)}):""}_archivedNote(){let e=this._compared.archived??0;if(!e)return"";let t=e===1?this._labels.plans_archived_one:this._labels.plans_archived_many;return h(t,{count:String(e)})}get _opened(){return this._openPlans??=new Set,this._openPlans}_afterRender(){this._listening||(this._listening=!0,this.shadowRoot.addEventListener("click",e=>{let s=e.target.closest?.("tr.figures")?.closest("tbody[data-plan]")?.dataset.plan;s&&(this._opened.has(s)?this._opened.delete(s):this._opened.add(s),this._render())}))}_bill(e,t){let{daily:s,demand:o}=e.breakdown,n=new Intl.NumberFormat(t.language,{maximumFractionDigits:2}),a=(d,p,m)=>W(t,{name:p,rate:h(this._labels.plans_per_day,{amount:u(d.rate,t)}),used:h(d.days===1?this._labels.plans_day:this._labels.plans_days,{days:n.format(d.days)}),amount:d.amount,side:"loss",key:m}),c=[a(s,this._labels.plans_daily,"daily"),...o?[a(o,this._labels.plans_demand,"demand")]:[],...this._importLines(e,t),...this._gridOnly?[]:this._exportLines(e,t),W(t,{name:this._labels.plans_total,money:ps("bill-total",e.total,this._labels,t),classes:"total"})],i=["",this._labels.plans_rate,this._labels.plans_used,this._labels.plans_amount].map(d=>`<th>${d}</th>`).join(""),l=e.breakdown.average_import_rate===null?"":us(this._labels.plans_average_note);return`<table class="bill"><thead><tr>${i}</tr></thead><tbody>${c.join("")}</tbody></table>${l}`}_rate(e,t){return`${ke(e,t)} ${xe(t)}`}_averageOf({kwh:e,amount:t},s){return e?h(this._labels.plans_average,{rate:this._rate(t/e,s)}):""}_importLines(e,t){let{imports:s}=e.breakdown,o=this._averageVerdict(e,t),n=this._labels[e.follows_prices?"plans_your_prices":"plans_market_price"],a=s.map((i,l)=>W(t,{name:i.rate===null?n:i.name||this._labels.plans_unnamed_price,rate:i.rate===null?this._averageOf(i,t):this._rate(i.rate,t),used:v(i.kwh,t),amount:i.amount,side:"loss",key:"import-"+l})),c=o?.colour?"box-shadow: inset 4px 0 0 "+o.colour.edge:"";return a.push(W(t,{name:this._labels.plans_energy,rate:this._average(e,t,"bill-average",o),used:v(ft(s,"kwh"),t),amount:e.energy,side:"loss",key:"energy",classes:"subtotal",style:c})),a}_exportLines(e,t){let{exports:s}=e.breakdown,o=s.map((a,c)=>W(t,{name:this._exportName(a,e),rate:a.rate===null?this._averageOf(a,t):this._rate(a.rate,t),used:v(a.kwh,t),amount:-a.amount,side:"gain",key:"export-"+c}));s.length>1&&o.push(W(t,{name:this._labels.plans_export,used:v(ft(s,"kwh"),t),amount:-ft(s,"amount"),side:"gain",key:"export",classes:"subtotal"}));let n=(e.export_unpaid??0)+(e.export_carried??0);return n>0&&o.push(W(t,{name:this._labels.plans_capped,amount:n,side:"loss",key:"capped"})),o}_exportName(e,t){return e.rate===null?this._labels[t.follows_prices?"plans_your_export_price":"plans_market_price"]:e.name?e.name:e.beyond_allowance?this._labels.plans_export_beyond:this._labels.plans_export_rate}_average(e,t,s,o=this._averageVerdict(e,t)){if(!o)return"";let n=o.colour?` style="color: ${o.colour.text}"`:"";return`<span class="average" data-figure="${s}"${n} title="${N(o.title)}">${o.text}</span>`}_averageVerdict(e,t){let s=e.breakdown,o=s?.average_import_rate;if(o==null)return;let n=p=>this._rate(p,t),a=s.cheapest_import_rate,c=s.dearest_import_rate,i=c-a,l=i>0?tt((c-o)/i,{dark:J(this)}):void 0,d=e.rates?.import_market?this._labels.plans_average_title_market:this._labels.plans_average_title;return{colour:l,text:h(this._labels.plans_average,{rate:n(o).replace(" ","\xA0")}),title:h(d,{average:n(o),cheapest:n(a),dearest:n(c)})}}_exportNotes(e,t){return[["unpaid",e.export_unpaid,this._labels.plans_export_unpaid],["carried",e.export_carried,this._labels.plans_export_carried]].filter(([,s])=>s>0).map(([s,o,n])=>`<div class="difference" data-figure="export-${s}:${e.id}">${h(n,{amount:u(o,t)})}</div>`).join("")}_resolution(e){let t=this._compared.five_minute_from;if(!t)return this._labels.plans_market_hourly;let s=new Date(t);return s<=this._period.start?this._labels.plans_market_five_minutes:h(this._labels.plans_market_from,{date:we(s,e)})}_total(e,t){return ps(`total:${e.id}`,e.total,this._labels,t,"total rule")}_part(e,{key:t,figure:s=t,group:o},n,a=""){if(t==="daily"&&e.daily_charge_missing)return`<td${se(a)} data-figure="${t}:${e.id}">${this._labels.plans_daily_missing}</td>`;if(t==="demand"&&!(s in e)){let m=e.demand_charge_missing?this._labels.plans_demand_missing:"";return`<td${se(a)} data-figure="${t}:${e.id}">${m}</td>`}let c=o==="earn"?"gain":"loss";if(t!=="energy"||!e.breakdown)return bt(`${t}:${e.id}`,e[s],n,{classes:a,side:c});let i=x(e[s],n)?c:"",l=[a,i].filter(Boolean).join(" "),d=this._average(e,n,"average:"+e.id),p=d?"<div>"+d+"</div>":"";return`<td${se(l)} data-figure="${t}:${e.id}">${u(e[s],n)}${p}</td>`}_difference(e,t,s){let o=t.total-e.total,n=x(o,s);if(!n)return`<td class="difference" data-figure="difference:${e.id}">${this._labels.plans_same_short}</td>`;let a=this._labels[n==="gain"?"plans_cheaper":"plans_dearer"],c=h(a,{amount:u(Math.abs(o),s)});return`<td class="difference ${n}" data-figure="difference:${e.id}">${c}</td>`}},us=r=>`<div class="hint">${r}</div>`,Xn=r=>new Intl.DateTimeFormat("en-CA",{year:"numeric",month:"2-digit",day:"2-digit",timeZone:r.timeZone}).format(new Date),Qn=(r,e)=>new Intl.DateTimeFormat(e.language,{day:"numeric",month:"short",timeZone:"UTC"}).format(new Date(`${r}T12:00:00Z`)),ft=(r,e)=>r.reduce((t,s)=>t+s[e],0),Jn=r=>r?` style="${r}"`:"",W=(r,{name:e,rate:t="",used:s="",amount:o,side:n,money:a,key:c,classes:i="",style:l=""})=>{let d=a??bt("bill-"+c,o,r,{side:n});return`<tr${se(i)}><th${Jn(l)}>${N(e)}</th><td>${t}</td><td>${s}</td>${d}</tr>`},se=r=>r?` class="${r}"`:"",bt=(r,e,t,{classes:s="",side:o=""}={})=>{let n=x(e,t)?e:0,a=[s,n?o:""].filter(Boolean).join(" ");return`<td${se(a)} data-figure="${r}">${u(n,t)}</td>`},ps=(r,e,t,s,o="")=>{if(x(-e,s)!=="gain")return bt(r,e,s,{classes:o,side:"loss"});let n=h(t.plans_in_credit,{amount:u(-e,s)});return`<td class="${[o,"gain"].filter(Boolean).join(" ")}" data-figure="${r}">${n}</td>`},ea=r=>r?`<span class="tags">${r}</span>`:"",N=r=>String(r).replaceAll(/[&<>"']/g,e=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[e]),yt=class extends f{},ta=()=>{b(_s,yt),y(ms,gt,{name:"Home Energy Advisor: Compare tariff plans",description:"What each tariff plan you have entered would have cost over the selected period, for the whole home."})};ta();var ys="hea-self-sufficiency-card",bs=`${ys}-editor`,fs=["energyUsed","energyFromGrid","energyFromGeneration","energyFromBattery","energyFromBatterySolar"],ra={maximumFractionDigits:0},gs=.005,vt=class extends F{static titleKey="title_self_sufficiency";static chartTag="ha-gauge";static bearingCard={type:"energy-self-sufficiency-gauge"};static emptyKey="no_energy_in_period";static cardStyle=`
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
  `;static getConfigElement(){return document.createElement(bs)}getCardSize(){return 4}_isEmpty(){return this._totals().energyUsed<=0}_totals(){return(this._result?.devices??[]).reduce((e,t)=>{for(let s of fs)e[s]+=t[s];return e},Object.fromEntries(fs.map(e=>[e,0])))}_shares(){let e=this._totals(),t=e.energyUsed,s=i=>e[i]/t,o=s("energyFromBatterySolar"),n=s("energyFromGeneration")+o,a=s("energyFromBattery")-o,c=s("energyFromGrid");return{generation:n,storedSolar:o,battery:a,grid:c,unaccounted:Math.max(0,1-n-a-c)}}_body(e){let t=super._body(e);return!this._chartReady||this._isEmpty()?t:`${t}${this._breakdown(e)}`}_gauges(){let e=this._shares(),t=this._totals().energyFromBattery>0;return[{key:"generation",label:this._labels.from_generation,note:e.storedSolar>gs?this._labels.including_stored_solar:"",colour:"var(--energy-solar-color, #ff9800)"},t&&{key:"storedSolar",label:this._labels.of_which_stored_solar,colour:"var(--energy-solar-color, #ff9800)"},t&&{key:"battery",label:this._labels.from_battery_grid,colour:"var(--energy-battery-out-color, #4db6ac)"},{key:"grid",label:this._labels.from_grid,colour:"var(--energy-grid-consumption-color, #488fc2)"}].filter(Boolean).map(s=>({...s,value:e[s.key]}))}_chartMarkup(){let e=K(this._hass),t=h(this._labels.energy_used_came_from,{energy:v(this._totals().energyUsed,e)}),s=this._gauges().map(({key:o,label:n,note:a,colour:c})=>`
        <div class="gauge">
          <ha-gauge data-gauge="${o}" style="--gauge-color: ${c}"></ha-gauge>
          <div class="headline">${n}</div>
          ${a?`<div class="headline">${a}</div>`:""}
        </div>`).join("");return`<div class="intro" data-figure="energy-used">${t}</div>
      <div class="gauges">${s}</div>`}_breakdown(e){let{unaccounted:t}=this._shares();return`${t>gs?`<div class="share">${this._labels.unaccounted}
            <span class="value" data-share="unaccounted">${Z(t,e)}</span></div>`:""}<div class="note">${this._labels.self_sufficiency_note}</div>`}_afterRender(){if(!this._chartReady||this._isEmpty())return;let e=Object.fromEntries(this._gauges().map(({key:t,value:s})=>[t,s]));for(let t of this.shadowRoot.querySelectorAll("ha-gauge"))t.hass=this._hass,t.min=0,t.max=100,t.value=e[t.dataset.gauge]*100,t.label="%",t.formatOptions=ra,t.locale=this._hass?.locale}},wt=class extends f{},sa=()=>{b(bs,wt),y(ys,vt,{name:"Home Energy Advisor: Self-sufficiency",description:"What share of the selected period's energy came from the household's own generation."})};sa();var vs="hea-sources-card",ws=`${vs}-editor`,oa=({energyFromGrid:r,energyUsed:e})=>e>0&&r>=0&&r<=e?r/e:void 0,na=[{field:"name",label:"device"},{field:"energyUsed",label:"energy",format:v},{field:"energyFromGrid",label:"grid",format:v},{field:"energyFromGeneration",label:"generation",format:v},{field:"energyFromBattery",label:"battery",format:v},{derive:oa,label:"from_grid",format:Z}],xs={energy_used:{field:"energyUsed",label:"energy_used"},energy_from_grid:{field:"energyFromGrid",label:"from_grid"},energy_from_generation:{field:"energyFromGeneration",label:"from_generation"},energy_from_battery:{field:"energyFromBattery",label:"from_battery"}},xt=class extends j{static titleKey="title_sources";static columns=na;static sorts=xs;static defaultSort="energy_used";static getConfigElement(){return document.createElement(ws)}},kt=class extends f{_extraSchema(){return Re(xs,E(this._hass))}},aa=()=>{b(ws,kt),y(vs,xt,{name:"Home Energy Advisor: Energy sources",description:"Grid, generation and battery behind each device's energy over the period."})};aa();var Es="hea-totals-card",Ss=`${Es}-editor`,ks=[{key:"actualCost",label:"paid"},{key:"costAtGridPrice",label:"would_have_paid"},{key:"costSavings",label:"saved"}],Et=class extends O{static titleKey="title_totals";static cardStyle=`${Ee}
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
  `;static getConfigElement(){return document.createElement(Ss)}getCardSize(){return 3}_body(e){let t=this._result?.totals;return`<div class="figures">${(this._result?.gridOnly?ks.slice(0,1):ks).map(({key:n,label:a})=>{let c=t?.[n],i=n==="costSavings"?x(c,e):"",l=i?` ${i}`:"";return`
        <div class="figure">
          <span class="label">${Se(a)}${this._labels[a]}</span>
          <span class="value${l}" data-figure="${n}">${u(c,e)}</span>
          ${this._comparedTo(n,c,e)}
        </div>`}).join("")}</div>`}_comparedTo(e,t,s){let o=this._result?.totals?.before?.[e];if(!Number.isFinite(o)||!Number.isFinite(t))return"";let n=V(e,t-o,s);return`<span class="${n?`compare ${n}`:"compare"}" data-compare="${e}">${h(this._labels.compared,{change:Y(t-o,s),before:u(o,s)})}</span>`}},St=class extends f{},ia=()=>{b(Ss,St),y(Es,Et,{name:"Home Energy Advisor: Totals",description:"What the selected period cost, what it would have cost at grid price, and the difference."})};ia();
