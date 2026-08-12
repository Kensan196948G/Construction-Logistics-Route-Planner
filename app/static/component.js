class Component extends DCLogic {
  state = {
    screen: null,
    activeRouteId: 'A',
    activeProjectId: null,
    selectedHazardId: null,
    layers: { bridge:true, school:true, traffic:true, disaster:true, narrow:true, data:true },
    checks: {},
    hazardStatus: {},
    reportFormat: 'markdown',
    vehicleType: 'trailer',
    clientType: 'public',
    timeWindow: 'daytime',
    nightAllowed: false,
    avoid: { school:true, residential:true, narrow:false, crossing:false, slope:false },
    kQuery: '', kSearching: false, kHasResult: false, kAnswer: '', kError: '',
    facCat: 'all',
    sys: { darkChrome:true, autoEval:true, cacheReuse:true, emailNotify:false, weeklyDigest:true, anonUsage:false },
    apiKey: '', apiStatus: 'untested', apiSaved: false,
    apiOnline: false,
    apiLoading: false,
    apiError: '',
    apiProjects: null,
    apiRoutes: null,
    apiReport: null,
    apiRisksByRoute: {},
    riskComment: '',
    apiNotice: '',
    apiAdminSources: null,
    apiAuditLogs: null,
    projectForm: {
      project_name:'', site_name:'', planner:'', owner_type:'public',
      start_name:'', start_lat:'35.681236', start_lng:'139.767125',
      dest_name:'', dest_lat:'35.658581', dest_lng:'139.745433',
      length_m:'12.0', width_m:'2.49', height_m:'3.8', gross_weight_t:'28.0', axle_weight_t:'10.0',
      cargo_type:'', special_vehicle:false, delivery_date:'', notes:'', time_window:'daytime'
    }
  };

  hexToRgba(hex, a){
    const h = (hex||'#ff6a00').replace('#','');
    const f = h.length===3 ? h.split('').map(c=>c+c).join('') : h;
    const n = parseInt(f,16);
    return 'rgba('+((n>>16)&255)+','+((n>>8)&255)+','+(n&255)+','+a+')';
  }
  setScreen(k){ this.setState({ screen:k, selectedHazardId:null }); }
  screenName(){ return this.state.screen || this.props.defaultScreen || 'dashboard'; }

  statusMeta(s){
    const m = {
      draft:{label:'作成中',bg:'#eef0f2',color:'#6b727c',border:'#d7dbe0'},
      evaluating:{label:'評価中',bg:'#e6effa',color:'#2b6cb0',border:'#c3d8ee'},
      review_required:{label:'追加確認中',bg:'#fce6da',color:'#d9531e',border:'#f3c3a8'},
      change_requested:{label:'差戻し',bg:'#f3e3f7',color:'#7b5ea7',border:'#d8b8e6'},
      reviewed:{label:'確認済み',bg:'#e4f3e9',color:'#1f8a4c',border:'#bfe3cf'},
      archived:{label:'保管',bg:'#eceae5',color:'#8a8f98',border:'#dcd8d0'}
    };
    return m[s] || m.draft;
  }
  rankMeta(r){
    const m = {
      A:{bg:'#e4f3e9',color:'#1f8a4c'}, B:{bg:'#e6effa',color:'#2b6cb0'},
      C:{bg:'#fbf0d8',color:'#b07d12'}, D:{bg:'#efe8f7',color:'#7b5ea7'}, E:{bg:'#eef0f2',color:'#79808a'}
    };
    return m[r] || m.E;
  }
  typeMeta(t){
    const m = {
      bridge:{k:'橋',label:'橋梁',color:'#d9531e'},
      tunnel:{k:'ト',label:'トンネル',color:'#d9531e'},
      underpass:{k:'ア',label:'アンダーパス',color:'#d9531e'},
      school:{k:'学',label:'学校',color:'#c47a00'},
      hospital:{k:'病',label:'病院',color:'#c47a00'},
      narrow:{k:'狭',label:'狭隘道路',color:'#c47a00'},
      traffic:{k:'交',label:'交通量',color:'#2b6cb0'},
      disaster:{k:'災',label:'災害リスク',color:'#7b5ea7'},
      crossing:{k:'踏',label:'踏切',color:'#7b5ea7'},
      data:{k:'?',label:'データ不足',color:'#5a6573'}
    };
    return m[t] || m.data;
  }
  srcStatusMeta(s){
    const m = {
      ok:{label:'正常',color:'#1f8a4c'}, warn:{label:'注意',color:'#c47a00'},
      partial:{label:'一部',color:'#5a6573'}, down:{label:'停止',color:'#c0271f'}
    };
    return m[s] || m.partial;
  }

  get projects(){
    if(this.state.apiProjects) return this.state.apiProjects;
    return [
      {id:'PRJ-2418', name:'第二期 護岸ブロック据付', site:'△△川 右岸 2.4k付近', status:'review_required', cands:4, confirm:3, data:2, updated:'06/18'},
      {id:'PRJ-2417', name:'橋梁桁 架設 重機回送', site:'国道○○号 △△高架下', status:'evaluating', cands:3, confirm:1, data:1, updated:'06/18'},
      {id:'PRJ-2411', name:'ボックスカルバート搬入', site:'市道□□線 ××地内', status:'reviewed', cands:5, confirm:0, data:0, updated:'06/16'},
      {id:'PRJ-2405', name:'クローラークレーン50t 回送', site:'臨港道路 ◇◇埠頭', status:'review_required', cands:4, confirm:2, data:3, updated:'06/15'},
      {id:'PRJ-2399', name:'PCa壁高欄 資材搬入', site:'県道△△線 トンネル前', status:'draft', cands:0, confirm:0, data:0, updated:'06/13'},
      {id:'PRJ-2390', name:'残土搬出 ダンプ運行計画', site:'造成地 A工区', status:'archived', cands:6, confirm:0, data:1, updated:'06/09'}
    ];
  }
  get dataSources(){
    if(this.state.apiAdminSources) return this.state.apiAdminSources;
    return [
      {name:'OpenStreetMap / Overpass', rank:'C', status:'ok', freq:'週次更新', checked:'06/19 06:12'},
      {name:'xROAD 道路データ', rank:'B', status:'warn', freq:'日次確認', checked:'06/19 06:10'},
      {name:'国土数値情報', rank:'B', status:'ok', freq:'月次取込', checked:'06/18 02:00'},
      {name:'PLATEAU 3D都市モデル', rank:'B', status:'partial', freq:'随時取込', checked:'06/14 11:30'},
      {name:'交通量データ', rank:'B', status:'ok', freq:'日次確認', checked:'06/19 06:12'}
    ];
  }
  get knowledgePoints(){
    return [
      {type:'bridge', name:'△△大橋（重量制限 要確認）', rank:'D', date:'06/18'},
      {type:'tunnel', name:'○○トンネル 高さ4.1m 表示', rank:'A', date:'06/17'},
      {type:'narrow', name:'市道□□線 狭隘区間 幅員不明', rank:'D', date:'06/16'},
      {type:'school', name:'××小学校 登下校 7:30-8:30', rank:'B', date:'06/15'}
    ];
  }
  get hazardBreakdown(){
    return [
      {type:'bridge', label:'橋梁・トンネル', n:14},
      {type:'school', label:'学校・病院', n:11},
      {type:'narrow', label:'狭隘道路', n:9},
      {type:'data', label:'データ不足', n:8},
      {type:'traffic', label:'交通量', n:7},
      {type:'disaster', label:'災害リスク', n:5}
    ];
  }

  selectRoute(id){ this.setState({ activeRouteId:id, selectedHazardId:null }); }
  selectHazard(id){ this.setState({ selectedHazardId:id }); }
  closeHazard(){ this.setState({ selectedHazardId:null }); }
  toggleLayer(k){ this.setState(s=>({ layers:Object.assign({}, s.layers, {[k]: !s.layers[k]}) })); }
  setHazardStatus(id, st){ this.setState(s=>({ hazardStatus:Object.assign({}, s.hazardStatus, {[id]: st}) })); }
  setVehicleType(v){ this.setState({ vehicleType:v }); }
  setClientType(c){ this.setState({ clientType:c }); }
  setTimeWindow(t){ this.setState({ timeWindow:t }); }
  toggleNight(){ this.setState(s=>({ nightAllowed:!s.nightAllowed })); }
  toggleAvoid(k){ this.setState(s=>({ avoid:Object.assign({}, s.avoid, {[k]: !s.avoid[k]}) })); }
  setReportFormat(f){ this.setState({ reportFormat:f }); }
  toggleCheck(k){ this.setState(s=>({ checks:Object.assign({}, s.checks, {[k]: !s.checks[k]}) })); }
  setFacCat(c){ this.setState({ facCat:c }); }
  toggleSys(k){ this.setState(s=>({ sys:Object.assign({}, s.sys, {[k]: !s.sys[k]}) })); }
  setApiKey(v){ this.setState({ apiKey:v, apiStatus:'untested', apiSaved:false }); }

  _authHeaders(){
    const headers = {};
    const key = this.state.apiKey || (typeof sessionStorage!=='undefined' ? sessionStorage.getItem('routePlannerApiKey')||'' : '');
    if(key && String(key).trim()) headers['Authorization'] = 'Bearer '+String(key).trim();
    return headers;
  }

  async testApi(){
    if(this.state.apiStatus==='testing') return;
    this.setState({ apiStatus:'testing' });
    try {
      const res = await fetch('/api/me', { headers: this._authHeaders() });
      this.setState({ apiStatus: res.ok ? 'ok' : 'fail', apiSaved:false });
    } catch(e){
      this.setState({ apiStatus:'fail' });
    }
  }
  saveApi(){
    try {
      if(typeof sessionStorage!=='undefined'){
        if(this.state.apiKey) sessionStorage.setItem('routePlannerApiKey', this.state.apiKey);
        else sessionStorage.removeItem('routePlannerApiKey');
      }
      this.setState({ apiSaved:true });
      setTimeout(()=>{ this.setState({ apiSaved:false }); }, 2200);
    } catch(e){
      this.setState({ apiError:'APIキーの保存に失敗しました。' });
    }
  }

  selectProject(projectId){
    this.setState({ activeProjectId:projectId, activeRouteId:'A', apiRoutes:null, apiRisksByRoute:{}, apiReport:null, apiError:'', apiNotice:'' });
    if(this._generatedFor === projectId){
      this.setScreen('routes');
      return;
    }
    this._generatedFor = projectId;
    this.generateAndEvaluate(projectId);
  }

  setRiskComment(v){ this.setState({ riskComment:v }); }

  async confirmRisk(routeId, riskId, status){
    if(!routeId || !riskId || this.state.riskConfirming) return;
    this.setState({ riskConfirming:true, apiError:'' });
    const comment = (this.state.riskComment||'').trim() || '画面から確認登録';
    try {
      const res = await fetch('/api/routes/'+encodeURIComponent(routeId)+'/risks/'+encodeURIComponent(riskId)+'/confirm', {
        method:'POST',
        headers: Object.assign({'Content-Type':'application/json'}, this._authHeaders()),
        body: JSON.stringify({ status, comment })
      });
      if(!res.ok) throw new Error('HTTP '+res.status);
      const data = await res.json();
      this.setState(s=>({
        riskConfirming:false,
        hazardStatus: Object.assign({}, s.hazardStatus, {[riskId]: data.status})
      }));
      return data;
    } catch(e){
      this.setState({ riskConfirming:false, apiError:'確認ステータスの登録に失敗しました。' });
      return null;
    }
  }

  async submitRiskComment(){
    const hazardId = this.state.selectedHazardId;
    if(!hazardId) return;
    const active = (this.routesData.find(r=>r.id===this.state.activeRouteId) || this.routesData[0] || {});
    const rawH = (this.hazardsByRoute[active.id]||[]).find(h=>h.id===hazardId);
    if(!rawH || !rawH.api) return;
    const status = this.state.hazardStatus[hazardId] || rawH.status || 'confirmed';
    const valid = ['confirmed','needs_review','not_applicable'].includes(status) ? status : 'confirmed';
    await this.confirmRisk(rawH.routeId, hazardId, valid);
  }

  setProjectFormField(k, v){
    this.setState(s=>({ projectForm: Object.assign({}, s.projectForm, {[k]: v}) }));
  }

  async fetchProjects(){
    this.setState({ apiLoading:true, apiError:'' });
    try {
      const res = await fetch('/api/projects', { headers: this._authHeaders() });
      if(!res.ok) throw new Error('HTTP '+res.status);
      const data = await res.json();
      const projects = (data||[]).map(p=>({
        id: p.id, name: p.project_name, site: p.site_name, status: p.status,
        cands: 0, confirm: 0, data: 0,
        updated: p.updated_at ? new Date(p.updated_at).toLocaleDateString('ja-JP',{month:'2-digit',day:'2-digit'}) : '—'
      }));
      this.setState({ apiProjects:projects, apiOnline:true, apiLoading:false });
    } catch(e){
      this.setState({ apiLoading:false, apiError:'案件一覧の取得に失敗しました。デモデータを表示します。' });
    }
  }

  async createProject(){
    const f = this.state.projectForm;
    if(!f.project_name||!f.site_name||!f.planner||!f.start_name||!f.dest_name){
      this.setState({ apiError:'工事件名・現場名・担当者・出発地・到着地は必須です。' });
      return null;
    }
    this.setState({ apiLoading:true, apiError:'' });
    try {
      const res = await fetch('/api/projects', {
        method:'POST', headers:Object.assign({'Content-Type':'application/json'}, this._authHeaders()),
        body: JSON.stringify({
          project_name: f.project_name, site_name: f.site_name, planner: f.planner,
          owner_type: this.state.clientType || 'public',
          start: { name: f.start_name, lat: parseFloat(f.start_lat), lng: parseFloat(f.start_lng) },
          destination: { name: f.dest_name, lat: parseFloat(f.dest_lat), lng: parseFloat(f.dest_lng) },
          vehicle: {
            vehicle_type:'heavy_truck',
            length_m: parseFloat(f.length_m)||null,
            width_m: parseFloat(f.width_m)||null,
            height_m: parseFloat(f.height_m)||null,
            gross_weight_t: parseFloat(f.gross_weight_t)||null,
            axle_weight_t: parseFloat(f.axle_weight_t)||null,
            cargo_type: f.cargo_type||null,
            special_vehicle_flag: !!f.special_vehicle
          },
          delivery: {
            delivery_date: f.delivery_date || null,
            time_window: this.state.timeWindow || 'daytime',
            holiday: false,
            night_delivery_allowed: this.state.nightAllowed || false
          },
          avoid_conditions: this._avoidPayload(),
          notes: f.notes || null
        })
      });
      if(!res.ok) throw new Error('HTTP '+res.status);
      const created = await res.json();
      this.setState({ activeProjectId: created.id });
      await this.fetchProjects();
      return created;
    } catch(e){
      this.setState({ apiLoading:false, apiError:'案件の作成に失敗しました。' });
      return null;
    }
  }

  _avoidPayload(){
    const map = {
      school:'schools', residential:'residential',
      crossing:'rail_crossings', slope:'steep_slopes'
    };
    const out = [];
    Object.keys(this.state.avoid||{}).forEach(k=>{
      if(this.state.avoid[k] && map[k]) out.push(map[k]);
    });
    return out;
  }

  async saveAndGenerate(){
    const created = await this.createProject();
    if(!created || !created.id){ this.setState({ apiLoading:false }); return; }
    await this.generateAndEvaluate(created.id);
  }

  async regenRoutes(){
    const pid = this.state.activeProjectId;
    if(!pid){
      this.setState({ apiError:'案件を選択してください（ダッシュボードの案件行から開くと選択されます）。' });
      return;
    }
    await this.generateAndEvaluate(pid);
  }

  async generateAndEvaluate(projectId){
    await this.generateRoutes(projectId);
    const routes = this.state.apiRoutes || [];
    if(!routes.length){
      this.setState({ apiLoading:false, apiNotice:'' });
      return;
    }
    for (let i=0;i<routes.length;i++){
      await this.evaluateRoute(routes[i].id);
    }
    this.setScreen('routes');
    this.setState({ apiNotice: routes.length ? 'ルート候補を生成し、リスク評価を実行しました。' : 'ルート候補を生成できませんでした。' });
  }

  async generateRoutes(projectId){
    this.setState({ apiLoading:true, apiError:'', apiRoutes:null });
    try {
      const res = await fetch('/api/projects/'+encodeURIComponent(projectId)+'/routes/generate', { method:'POST', headers:Object.assign({'Content-Type':'application/json'}, this._authHeaders()), body:'{}' });
      if(!res.ok) throw new Error('HTTP '+res.status);
      const data = await res.json();
      const routes = (data.routes||[]).map((r,i)=>{
        const letters = ['A','B','C','D','E'];
        return {
          id: r.id, letter: letters[i]||'?', name: r.name, typeLabel: r.route_type,
          distance: String(r.distance_km||0), duration: String(r.duration_min||0),
          level: r.risk_level||'data_insufficient', score: r.risk_score||0,
          counts: {confirm:0,caution:0,data:1},
          arterial: 50, residential: '—', bridges: 0, tunnels: 0,
          concern: r.summary||'評価待ち',
          d: this._routeD(i),
          geometry: Array.isArray(r.geometry) ? r.geometry : [],
          breakdown: [{label:'評価待ち',v:0,m:100}]
        };
      });
      const apiRouteKeyMap = {};
      routes.forEach(r=>{ apiRouteKeyMap[r.id] = r.letter; });
      this.setState({ apiRoutes:routes, apiRouteKeyMap, apiRisksByRoute:{}, apiLoading:false, activeRouteId: routes[0]?routes[0].id:'A' });
    } catch(e){
      this.setState({ apiLoading:false, apiError:'ルート生成に失敗しました。' });
    }
  }

  async evaluateRoute(routeId){
    this.setState({ apiLoading:true, apiError:'' });
    try {
      const res = await fetch('/api/routes/'+encodeURIComponent(routeId)+'/evaluate', { method:'POST', headers:Object.assign({'Content-Type':'application/json'}, this._authHeaders()), body:'{}' });
      if(!res.ok) throw new Error('HTTP '+res.status);
      const data = await res.json();
      const apiRisksByRoute = Object.assign({}, this.state.apiRisksByRoute, {[routeId]: data.risks||[]});
      const routes = (this.state.apiRoutes||[]).map(r=>{
        if(r.id!==routeId) return r;
        return Object.assign({}, r, {
          level: data.risk_level, score: data.risk_score,
          concern: data.summary||'',
          counts: {
            confirm: (data.risk_counts||{}).confirm_required||0,
            caution: (data.risk_counts||{}).caution||0,
            data: (data.risk_counts||{}).data_insufficient||0
          }
        });
      });
      this.setState({ apiRoutes:routes, apiRisksByRoute, apiLoading:false });
    } catch(e){
      this.setState({ apiLoading:false, apiError:'評価に失敗しました。' });
    }
  }

  async fetchReport(projectId, format){
    this.setState({ apiLoading:true, apiError:'', apiReport:null });
    try {
      const res = await fetch('/api/projects/'+encodeURIComponent(projectId)+'/report?format='+(format||'markdown'), { headers: this._authHeaders() });
      if(!res.ok) throw new Error('HTTP '+res.status);
      const data = await res.json();
      this.setState({ apiReport:data.content, apiLoading:false, apiNotice:'レポートを取得しました。' });
    } catch(e){
      this.setState({ apiLoading:false, apiError:'レポート生成に失敗しました。' });
    }
  }

  setReportFormatWithFetch(f){
    this.setState({ reportFormat:f });
    if(this.state.activeProjectId && (f==='markdown' || f==='csv')){
      this.fetchReport(this.state.activeProjectId, f);
    }
  }

  async downloadReport(format){
    const pid = this.state.activeProjectId;
    if(!pid){
      this.setState({ apiError:'案件を選択してください（ダッシュボードの案件行から開くと選択されます）。' });
      return;
    }
    this.setState({ apiLoading:true, apiError:'' });
    try {
      const url = '/api/projects/'+encodeURIComponent(pid)+'/report?format='+(format||'markdown');
      const res = await fetch(url, { headers: this._authHeaders() });
      if(!res.ok) throw new Error('HTTP '+res.status);
      if(format==='pdf'){
        const blob = await res.blob();
        this._downloadBlob(blob, 'route-report-'+pid+'.pdf');
      } else {
        const data = await res.json();
        const blob = new Blob([data.content||''], { type:'text/plain;charset=utf-8' });
        this._downloadBlob(blob, 'route-report-'+pid+'.'+(format==='csv'?'csv':'md'));
        this.setState({ apiReport: data.content||'', apiLoading:false });
        return;
      }
      this.setState({ apiLoading:false });
    } catch(e){
      this.setState({ apiLoading:false, apiError:'レポートのダウンロードに失敗しました。' });
    }
  }

  _downloadBlob(blob, filename){
    if(typeof document==='undefined' || typeof URL==='undefined') return;
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename;
    document.body.appendChild(a); a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  async submitProject(){
    const pid = this.state.activeProjectId;
    if(!pid){ this.setState({ apiError:'案件を選択してください。' }); return; }
    this.setState({ apiLoading:true, apiError:'', apiNotice:'' });
    try {
      const res = await fetch('/api/projects/'+encodeURIComponent(pid)+'/submit', {
        method:'POST', headers:Object.assign({'Content-Type':'application/json'}, this._authHeaders()),
        body: JSON.stringify({ comment: '画面からレビュー依頼' })
      });
      if(!res.ok) throw new Error('HTTP '+res.status);
      await this.fetchProjects();
      this.setState({ apiLoading:false, apiNotice:'レビュー依頼（提出）しました。承認者による確認を待ってください。' });
    } catch(e){
      this.setState({ apiLoading:false, apiError:'提出に失敗しました（未評価のルートがある場合は先に評価してください）。' });
    }
  }

  async approveProject(){
    const pid = this.state.activeProjectId;
    if(!pid){ this.setState({ apiError:'案件を選択してください。' }); return; }
    this.setState({ apiLoading:true, apiError:'', apiNotice:'' });
    try {
      const res = await fetch('/api/projects/'+encodeURIComponent(pid)+'/approve', {
        method:'POST', headers:Object.assign({'Content-Type':'application/json'}, this._authHeaders()),
        body: JSON.stringify({ comment: '画面から承認' })
      });
      if(!res.ok) throw new Error('HTTP '+res.status);
      await this.fetchProjects();
      this.setState({ apiLoading:false, apiNotice:'案件を承認しました。' });
    } catch(e){
      this.setState({ apiLoading:false, apiError:'承認に失敗しました（管理者権限・提出済みステータスが必要です）。' });
    }
  }

  async fetchAuditLogs(){
    try {
      const res = await fetch('/api/admin/audit-logs?limit=100', { headers: this._authHeaders() });
      if(!res.ok) return;
      const data = await res.json();
      const logs = (data||[]).map(l=>({
        t: l.created_at ? new Date(l.created_at).toLocaleString('ja-JP',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'}) : '—',
        u: l.user_id||'—', a: l.action||'—', tg: l.target_id||'—'
      }));
      this.setState({ apiAuditLogs: logs });
    } catch(e){ /* keep demo rows */ }
  }

  async fetchDataSources(){
    try {
      const res = await fetch('/api/admin/data-sources', { headers: this._authHeaders() });
      if(!res.ok) return;
      const data = await res.json();
      const srcs = (data||[]).map(d=>{
        const ss = this.srcStatusMeta(d.status==='configured'?'ok':(d.status==='stub'?'warn':'partial'));
        const rm = this.rankMeta('C');
        return {
          name: d.name||d.id, statusLabel:ss.label, statusColor:ss.color,
          dotColor:ss.color, dotHalo:this.hexToRgba(ss.color,0.18),
          rankLabel:'C', rankBg:rm.bg, rankColor:rm.color,
          freq:'—', checked:'—', status:d.status,
          toggleBg:'#cdd2d8', toggleX:'2px'
        };
      });
      this.setState({ apiAdminSources: srcs });
    } catch(e){ /* keep demo rows */ }
  }

  _routeD(i){
    const paths = [
      'M110,650 L180,650 L180,500 L360,500 L360,330 L640,330 L640,170 L890,170 L890,140',
      'M110,650 L150,650 L150,330 L640,330 L640,170 L890,170 L890,140',
      'M110,650 L110,210 L430,210 L430,95 L890,95 L890,140',
      'M110,650 L420,650 L420,500 L540,500 L540,330 L660,330 L660,170 L890,170 L890,140'
    ];
    return paths[i] || paths[0];
  }

  async runKnowledgeSearch(){
    const q = (this.state.kQuery||'').trim();
    if(!q || this.state.kSearching) return;
    this.setState({ kSearching:true, kHasResult:true, kError:'', kAnswer:'' });
    try {
      const res = await fetch('/api/knowledge/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: q })
      });
      if(!res.ok) throw new Error('http ' + res.status);
      const data = await res.json();
      if((this.state.kQuery||'').trim() !== q){ this.setState({ kSearching:false }); return; }
      let text = (data.answer || '').trim();
      const targets = Array.isArray(data.confirmation_targets) ? data.confirmation_targets : [];
      if(targets.length){
        text += '\n\n追加確認事項:\n' + targets.map(t=>'・' + t).join('\n');
      }
      this.setState({ kAnswer: text, kSearching:false });
    } catch(e){
      if((this.state.kQuery||'').trim() !== q){ this.setState({ kSearching:false }); return; }
      this.setState({ kSearching:false, kError:'検索を実行できませんでした。時間をおいて再度お試しください。' });
    }
  }
  quickSearch(q){ this.setState({ kQuery:q }, ()=>this.runKnowledgeSearch()); }

  get facilityPoints(){
    return [
      {type:'bridge', name:'△△大橋', loc:'国道○○号 12.3k', rank:'D', records:'通行実績 3件 ／ 28t 可（R02確認）', note:'重量制限標識なし。管理者台帳で耐荷重を確認済み。'},
      {type:'tunnel', name:'○○トンネル', loc:'県道△△線', rank:'A', records:'制限高 4.1m', note:'高さ4.1m標識あり。トレーラー嵩上げ時は要注意。'},
      {type:'narrow', name:'市道□□線 狭隘区間', loc:'××地内 0.4km', rank:'D', records:'すれ違い不可', note:'有効幅員2.6m。誘導員必須。待避所 2 箇所あり。'},
      {type:'school', name:'××小学校', loc:'△△町', rank:'B', records:'登下校 7:30-8:30 / 15:00-16:00', note:'通学路と重複。当該時間帯を回避。'},
      {type:'hospital', name:'市立△△病院', loc:'△△町2丁目', rank:'B', records:'救急動線あり', note:'正面玄関前の停車・待機は不可。'},
      {type:'crossing', name:'JR□□線 △△踏切', loc:'市道□□線', rank:'D', records:'朝ピーク 遮断時間 長め', note:'大型は前後の取り回しに注意。'},
      {type:'disaster', name:'△△川 浸水想定区域', loc:'右岸一帯', rank:'B', records:'計画規模 浸水想定', note:'荒天時は搬入延期を判断。'},
      {type:'traffic', name:'国道○○号 △△交差点', loc:'△△町', rank:'B', records:'朝夕混雑', note:'右折レーン短い。誘導員を推奨。'}
    ];
  }

  levelMeta(l){
    const m={
      candidate:{label:'利用候補',color:'#1f8a4c',bg:'#e4f3e9',border:'#bfe3cf'},
      caution:{label:'注意',color:'#c47a00',bg:'#fbf0d8',border:'#f0d39a'},
      confirm_required:{label:'要確認',color:'#d9531e',bg:'#fce6da',border:'#f3c3a8'},
      exclusion_consideration:{label:'除外検討',color:'#c0271f',bg:'#f9e2e0',border:'#ecb1ab'},
      exclusion_candidate:{label:'除外検討',color:'#c0271f',bg:'#f9e2e0',border:'#ecb1ab'},
      data_insufficient:{label:'データ不足',color:'#5a6573',bg:'#eceef1',border:'#ccd2da'}
    };
    return m[l] || m.data_insufficient;
  }
  hzStatusMeta(s){
    const m={
      unconfirmed:{label:'未確認',color:'#7c828c'},
      checking:{label:'確認中',color:'#2b6cb0'},
      confirmed:{label:'確認済み',color:'#1f8a4c'},
      needs_review:{label:'要再確認',color:'#d9531e'},
      not_applicable:{label:'対象外',color:'#9aa0a7'},
      confirmed_ok:{label:'確認済(懸念低)',color:'#1f8a4c'},
      confirmed_ng:{label:'確認済(懸念高)',color:'#c0271f'},
    };
    return m[s] || m.unconfirmed;
  }
  layerGroup(t){
    if(t==='bridge'||t==='tunnel'||t==='underpass') return 'bridge';
    if(t==='school'||t==='hospital') return 'school';
    if(t==='narrow') return 'narrow';
    if(t==='traffic') return 'traffic';
    if(t==='disaster') return 'disaster';
    return 'data';
  }

  get routesData(){
    if(this.state.apiRoutes) return this.state.apiRoutes;
    return [
      {id:'A',letter:'A',name:'距離優先ルート',typeLabel:'距離優先',distance:'12.4',duration:'34',level:'confirm_required',score:64,counts:{confirm:2,caution:5,data:1},arterial:38,residential:'あり',bridges:1,tunnels:1,
        concern:'橋梁の重量制限とトンネル高さが公開データ上で未確認です。',
        d:'M110,650 L180,650 L180,500 L360,500 L360,330 L640,330 L640,170 L890,170 L890,140',
        breakdown:[{label:'橋梁・トンネル・高さ重量',v:21,m:25},{label:'道路条件・狭隘性',v:13,m:20},{label:'交通量・混雑',v:11,m:15},{label:'周辺施設・近隣影響',v:11,m:15},{label:'災害・地形リスク',v:5,m:10},{label:'データ不足',v:3,m:10}]},
      {id:'B',letter:'B',name:'幹線道路優先ルート',typeLabel:'幹線優先',distance:'15.1',duration:'38',level:'caution',score:41,counts:{confirm:1,caution:3,data:1},arterial:74,residential:'一部',bridges:1,tunnels:1,
        concern:'幹線中心で懸念は少なめ。朝夕の交通量ピークに注意。',
        d:'M110,650 L150,650 L150,330 L640,330 L640,170 L890,170 L890,140',
        breakdown:[{label:'橋梁・トンネル・高さ重量',v:14,m:25},{label:'道路条件・狭隘性',v:9,m:20},{label:'交通量・混雑',v:8,m:15},{label:'周辺施設・近隣影響',v:5,m:15},{label:'災害・地形リスク',v:3,m:10},{label:'データ不足',v:2,m:10}]},
      {id:'C',letter:'C',name:'住宅地回避ルート',typeLabel:'住宅地回避',distance:'17.2',duration:'46',level:'candidate',score:29,counts:{confirm:0,caution:2,data:2},arterial:60,residential:'回避',bridges:1,tunnels:0,
        concern:'住宅地・学校を回避。距離は長いが近隣影響は小さい候補。',
        d:'M110,650 L110,210 L430,210 L430,95 L890,95 L890,140',
        breakdown:[{label:'橋梁・トンネル・高さ重量',v:6,m:25},{label:'道路条件・狭隘性',v:7,m:20},{label:'交通量・混雑',v:5,m:15},{label:'周辺施設・近隣影響',v:4,m:15},{label:'災害・地形リスク',v:2,m:10},{label:'データ不足',v:5,m:10}]},
      {id:'D',letter:'D',name:'橋梁・トンネル確認重視',typeLabel:'構造物確認',distance:'14.0',duration:'41',level:'confirm_required',score:70,counts:{confirm:4,caution:3,data:1},arterial:52,residential:'一部',bridges:2,tunnels:1,
        concern:'橋梁2・トンネル1・アンダーパス1。耐荷重と高さの確認項目が多い。',
        d:'M110,650 L420,650 L420,500 L540,500 L540,330 L660,330 L660,170 L890,170 L890,140',
        breakdown:[{label:'橋梁・トンネル・高さ重量',v:24,m:25},{label:'道路条件・狭隘性',v:12,m:20},{label:'交通量・混雑',v:10,m:15},{label:'周辺施設・近隣影響',v:10,m:15},{label:'災害・地形リスク',v:8,m:10},{label:'データ不足',v:6,m:10}]}
    ];
  }
  get hazardsByRoute(){
    const demo = {
      A:[
        {id:'A1',type:'narrow',name:'市道□□線 狭隘区間',level:'caution',x:180,y:575,rank:'C',source:'OpenStreetMap',fetched:'2026/06/18 06:12',summary:'道路幅員の属性が無く、狭隘の可能性があります。すれ違い困難の懸念。',reco:'現地で有効幅員・待避所を確認。誘導員配置とすれ違い計画を検討。',status:'unconfirmed'},
        {id:'A2',type:'hospital',name:'市立△△病院',level:'caution',x:270,y:500,rank:'B',source:'国土数値情報',fetched:'2026/06/18 02:00',summary:'病院から約180m。搬入時間帯・騒音・救急動線への配慮が必要です。',reco:'救急出入口を回避。搬入時間帯を病院運用と調整。',status:'unconfirmed'},
        {id:'A3',type:'school',name:'××小学校',level:'caution',x:360,y:420,rank:'B',source:'国土数値情報',fetched:'2026/06/18 02:00',summary:'学校から約260m。登下校時間帯(7:30-8:30 / 15:00-16:00)は注意。',reco:'登下校時間帯を避ける。通学路との重複区間を確認。',status:'checking'},
        {id:'A4',type:'disaster',name:'〇〇川 浸水想定区域',level:'caution',x:445,y:330,rank:'B',source:'国土数値情報(浸水想定)',fetched:'2026/06/17 02:00',summary:'計画規模の浸水想定区域に近接。荒天時は搬入延期判断が必要。',reco:'搬入日の気象・河川水位を確認。代替日を準備。',status:'unconfirmed'},
        {id:'A5',type:'bridge',name:'〇〇川 △△橋',level:'confirm_required',x:520,y:330,rank:'C',source:'OpenStreetMap',fetched:'2026/06/18 06:12',summary:'橋梁を通過しますが、公開データ上で重量制限を確認できません。',reco:'道路管理者へ橋梁の耐荷重・通行可否を確認。設計図書を照会。',status:'unconfirmed'},
        {id:'A6',type:'tunnel',name:'△△トンネル',level:'confirm_required',x:640,y:250,rank:'C',source:'OpenStreetMap',fetched:'2026/06/18 06:12',summary:'トンネル区間で高さ制限の属性が確認できません。',reco:'制限高さの標識・道路台帳を確認。車両全高との余裕を照合。',status:'unconfirmed'},
        {id:'A7',type:'traffic',name:'国道○○号 △△交差点',level:'caution',x:720,y:170,rank:'B',source:'xROAD 交通量',fetched:'2026/06/19 06:10',summary:'交通量が多い区間。朝夕ピークの右左折負荷に注意。',reco:'ピーク時間帯を回避。誘導員・待機場所を確保。',status:'unconfirmed'},
        {id:'A8',type:'data',name:'県道△△線 属性欠損区間',level:'data_insufficient',x:820,y:170,rank:'C',source:'OpenStreetMap',fetched:'2026/06/18 06:12',summary:'道路種別・幅員などの属性が欠損しており判断できません。',reco:'現地踏査または道路管理者へ確認。',status:'unconfirmed'}
      ],
      B:[
        {id:'B1',type:'traffic',name:'臨港道路 交通量注意',level:'caution',x:150,y:470,rank:'B',source:'xROAD 交通量',fetched:'2026/06/19 06:10',summary:'幹線で交通量が多い区間。',reco:'ピーク時間帯を回避。',status:'unconfirmed'},
        {id:'B2',type:'disaster',name:'〇〇川 浸水想定区域',level:'caution',x:440,y:330,rank:'B',source:'国土数値情報(浸水想定)',fetched:'2026/06/17 02:00',summary:'浸水想定区域に近接。',reco:'気象・水位を確認。',status:'unconfirmed'},
        {id:'B3',type:'bridge',name:'〇〇川 △△橋',level:'confirm_required',x:520,y:330,rank:'C',source:'OpenStreetMap',fetched:'2026/06/18 06:12',summary:'橋梁の重量制限が未確認です。',reco:'道路管理者へ耐荷重を確認。',status:'unconfirmed'},
        {id:'B4',type:'school',name:'△△中学校',level:'caution',x:640,y:260,rank:'B',source:'国土数値情報',fetched:'2026/06/18 02:00',summary:'学校近接。登下校時間帯に注意。',reco:'時間帯を調整。',status:'unconfirmed'},
        {id:'B5',type:'data',name:'県道△△線 属性欠損区間',level:'data_insufficient',x:760,y:170,rank:'C',source:'OpenStreetMap',fetched:'2026/06/18 06:12',summary:'道路属性が欠損しています。',reco:'現地確認。',status:'unconfirmed'}
      ],
      C:[
        {id:'C1',type:'traffic',name:'外周道路 合流部',level:'caution',x:110,y:360,rank:'B',source:'xROAD 交通量',fetched:'2026/06/19 06:10',summary:'合流部で交通量に注意。',reco:'誘導員配置を検討。',status:'unconfirmed'},
        {id:'C2',type:'narrow',name:'迂回区間 幅員不明',level:'caution',x:430,y:160,rank:'C',source:'OpenStreetMap',fetched:'2026/06/18 06:12',summary:'迂回区間で幅員が不明。',reco:'現地で幅員を確認。',status:'unconfirmed'},
        {id:'C3',type:'data',name:'郊外道路 属性欠損',level:'data_insufficient',x:620,y:95,rank:'C',source:'OpenStreetMap',fetched:'2026/06/18 06:12',summary:'道路属性が欠損しています。',reco:'現地確認。',status:'unconfirmed'},
        {id:'C4',type:'data',name:'橋梁有無 不明区間',level:'data_insufficient',x:800,y:95,rank:'C',source:'OpenStreetMap',fetched:'2026/06/18 06:12',summary:'構造物の有無が判断できません。',reco:'地図・現地で確認。',status:'unconfirmed'}
      ],
      D:[
        {id:'D1',type:'school',name:'××小学校',level:'caution',x:420,y:560,rank:'B',source:'国土数値情報',fetched:'2026/06/18 02:00',summary:'学校近接。登下校時間帯に注意。',reco:'時間帯を調整。',status:'unconfirmed'},
        {id:'D2',type:'disaster',name:'低地・浸水想定',level:'caution',x:480,y:500,rank:'B',source:'国土数値情報(浸水想定)',fetched:'2026/06/17 02:00',summary:'低地で浸水想定に近接。',reco:'気象・水位を確認。',status:'unconfirmed'},
        {id:'D3',type:'bridge',name:'第一 △△橋',level:'confirm_required',x:540,y:500,rank:'C',source:'OpenStreetMap',fetched:'2026/06/18 06:12',summary:'橋梁の重量制限が未確認です。',reco:'道路管理者へ耐荷重を確認。',status:'unconfirmed'},
        {id:'D4',type:'bridge',name:'第二 □□橋',level:'confirm_required',x:540,y:400,rank:'C',source:'OpenStreetMap',fetched:'2026/06/18 06:12',summary:'橋梁の重量制限が未確認です。',reco:'道路管理者へ耐荷重を確認。',status:'unconfirmed'},
        {id:'D5',type:'underpass',name:'△△アンダーパス',level:'confirm_required',x:620,y:330,rank:'C',source:'OpenStreetMap',fetched:'2026/06/18 06:12',summary:'アンダーパスの制限高さが未確認です。',reco:'制限高さを現地・台帳で確認。',status:'unconfirmed'},
        {id:'D6',type:'tunnel',name:'△△トンネル',level:'confirm_required',x:660,y:250,rank:'C',source:'OpenStreetMap',fetched:'2026/06/18 06:12',summary:'トンネルの高さ制限が未確認です。',reco:'制限高さを確認。',status:'unconfirmed'},
        {id:'D7',type:'traffic',name:'国道○○号 △△交差点',level:'caution',x:720,y:170,rank:'B',source:'xROAD 交通量',fetched:'2026/06/19 06:10',summary:'交通量が多い区間。',reco:'ピークを回避。',status:'unconfirmed'},
        {id:'D8',type:'data',name:'県道△△線 属性欠損区間',level:'data_insufficient',x:820,y:170,rank:'C',source:'OpenStreetMap',fetched:'2026/06/18 06:12',summary:'道路属性が欠損しています。',reco:'現地確認。',status:'unconfirmed'}
      ]
    };
    return this._hazardsWithApi(demo);
  }

  _hazardsWithApi(demo){
    const apiRisks = this.state.apiRisksByRoute || {};
    const routeKeys = this.state.apiRouteKeyMap || {};
    if(!Object.keys(apiRisks).length) return demo;
    const out = Object.assign({}, demo);
    Object.keys(apiRisks).forEach(realId=>{
      const letter = routeKeys[realId];
      if(!letter) return;
      const mapped = (apiRisks[realId]||[]).map((r,i)=>this._apiHazard(r, realId, i)).filter(Boolean);
      if(mapped.length) out[letter] = mapped;
    });
    return out;
  }

  _apiHazard(risk, realRouteId, index){
    const feature = risk && risk.feature;
    if(!feature || typeof feature.lat==='undefined') return null;
    const [x, y] = this._geoInv(feature.lat, feature.lng);
    if(x < -50 || x > 1050 || y < -50 || y > 770) return null;
    const type = feature.feature_type==='osm_quality' ? 'data' : feature.feature_type;
    return {
      id: risk.id || ('risk-'+index),
      routeId: realRouteId,
      type,
      name: risk.title || feature.name,
      level: risk.level || 'data_insufficient',
      x, y,
      rank: feature.data_quality || 'C',
      source: feature.source || '公開データ',
      fetched: feature.acquired_at || '',
      summary: risk.message || '',
      reco: risk.confirmation_target || '',
      status: risk.confirmation_status || 'unconfirmed',
      api: true
    };
  }

  _geo(x, y){
    const WEST=139.72, EAST=139.80, NORTH=35.69, SOUTH=35.63;
    return [ NORTH - (y/720)*(NORTH-SOUTH), WEST + (x/1000)*(EAST-WEST) ];
  }
  _geoInv(lat, lng){
    const WEST=139.72, EAST=139.80, NORTH=35.69, SOUTH=35.63;
    return [ (lng-WEST)/(EAST-WEST)*1000, (NORTH-lat)/(NORTH-SOUTH)*720 ];
  }
  _pathLatLngs(d){
    const pts=[]; const re=/[ML]\s*(-?\d+(?:\.\d+)?)[ ,]+(-?\d+(?:\.\d+)?)/g; let m;
    while((m=re.exec(d))) pts.push(this._geo(parseFloat(m[1]), parseFloat(m[2])));
    return pts;
  }
  _esc(s){ return String(s==null?'':s).replace(/[&<>"]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
  _endpointIcon(label, bg, ring){
    const border = ring ? ('border:2px solid '+ring+';') : 'border:2px solid #fff;';
    return L.divIcon({ className:'', iconSize:[28,28], iconAnchor:[14,14],
      html:'<div style="width:28px;height:28px;border-radius:50%;background:'+bg+';'+border+
        'color:#fff;font:700 12px \'Noto Sans JP\',sans-serif;display:flex;align-items:center;justify-content:center;box-shadow:0 1px 4px rgba(0,0,0,.4)">'+label+'</div>' });
  }
  _hazardIcon(k, color, sel){
    const size = sel?34:28; const ring = sel?'box-shadow:0 0 0 3px #ff6a00;':'box-shadow:0 1px 4px rgba(0,0,0,.4);';
    return L.divIcon({ className:'', iconSize:[size,size], iconAnchor:[size/2,size],
      html:'<div style="width:'+size+'px;height:'+size+'px;border-radius:7px 7px 7px 1px;background:'+color+
        ';border:2px solid #fff;'+ring+'color:#fff;font:700 14px \'Noto Sans JP\',sans-serif;display:flex;align-items:center;justify-content:center">'+k+'</div>' });
  }
  afterRender(){
    if(typeof L==='undefined') return;
    if(this.screenName()!=='routes') return;
    const el = document.getElementById('route-map');
    if(!el) return;
    if(!this._map){
      const osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom:19, attribution:'© OpenStreetMap contributors' });
      this._map = L.map(el, { zoomControl:false, attributionControl:false, center:[35.66,139.76], zoom:13, layers:[osm] });
      this._routeLayer = L.layerGroup().addTo(this._map);
      this._hazardLayer = L.layerGroup().addTo(this._map);
      this._endpointLayer = L.layerGroup().addTo(this._map);
      this._fitFor = null;
    } else {
      this._map.invalidateSize();
    }
    this._drawMap();
  }
  _drawMap(){
    const routes = this.routesData || [];
    const active = routes.find(r=>r.id===this.state.activeRouteId) || routes[0];
    if(!active) return;

    const latLngsOf = (r)=>{
      if(Array.isArray(r.geometry) && r.geometry.length>=2){
        return r.geometry.map(g=>[Number(g.lat), Number(g.lng)]);
      }
      return this._pathLatLngs(r.d);
    };

    this._routeLayer.clearLayers();
    routes.forEach(r=>{ if(r.id===active.id) return;
      const pts = latLngsOf(r);
      if(pts.length) L.polyline(pts, { color:'#8d96a1', weight:3, dashArray:'2 8', opacity:0.8 }).addTo(this._routeLayer); });
    const pts = latLngsOf(active);
    L.polyline(pts, { color:'#ffffff', weight:9 }).addTo(this._routeLayer);
    L.polyline(pts, { color:'#1559b8', weight:5 }).addTo(this._routeLayer);

    this._endpointLayer.clearLayers();
    L.marker(this._geo(110,650), { icon:this._endpointIcon('発','#1f8a4c') }).bindPopup('出発地').addTo(this._endpointLayer);
    L.marker(this._geo(890,140), { icon:this._endpointIcon('現','#1a1d21','#ff6a00') }).bindPopup('現場（到着）').addTo(this._endpointLayer);

    this._hazardLayer.clearLayers();
    const layers = this.state.layers;
    (this.hazardsByRoute[active.id]||[]).filter(h=>layers[this.layerGroup(h.type)]).forEach(h=>{
      const tm=this.typeMeta(h.type), lm=this.levelMeta(h.level), sel=h.id===this.state.selectedHazardId;
      const marker = L.marker(this._geo(h.x,h.y), { icon:this._hazardIcon(tm.k, lm.color, sel) });
      marker.bindPopup('<b>'+this._esc(h.name)+'</b><br>'+this._esc(lm.label)+' · '+this._esc(tm.label)+
        '<br>'+this._esc(h.summary||'')+'<br><span style="color:#9aa0a7">出典: '+this._esc(h.source||'')+'</span>');
      marker.on('click', ()=>this.selectHazard(h.id));
      this._hazardLayer.addLayer(marker);
    });

    if(this._fitFor!==active.id && pts.length){
      this._map.fitBounds(L.latLngBounds(pts).pad(0.25));
      this._fitFor = active.id;
    }
  }

  renderVals(){
    const accent = this.props.accent || '#ff6a00';
    const soft = this.hexToRgba(accent, 0.14);
    const screen = this.screenName();
    const mk = (k)=>({ bg: screen===k?soft:'transparent', fg: screen===k?'#ffffff':'#99a0ab', bar: screen===k?accent:'transparent', go: ()=>this.setScreen(k) });

    const facCats = [
      {key:'all',label:'すべて'},{key:'bridge',label:'橋梁'},{key:'tunnel',label:'トンネル'},{key:'narrow',label:'狭隘'},{key:'school',label:'学校'},{key:'hospital',label:'病院'},{key:'crossing',label:'踏切'},{key:'disaster',label:'災害'},{key:'traffic',label:'交通'}
    ].map(c=>{ const on=this.state.facCat===c.key; const cnt = c.key==='all'?this.facilityPoints.length:this.facilityPoints.filter(f=>f.type===c.key).length; return Object.assign({}, c, {on, count:cnt, onClick:()=>this.setFacCat(c.key), bg:on?'#1a1d21':'#fff', fg:on?'#fff':'#5e646c', border:on?'#1a1d21':'#d4cfc4'}); });
    const facilities = this.facilityPoints.filter(f=>this.state.facCat==='all'||f.type===this.state.facCat).map(f=>{ const tm=this.typeMeta(f.type); const rm=this.rankMeta(f.rank); return Object.assign({}, f, {k:tm.k, typeLabel:tm.label, color:tm.color, rankLabel:f.rank, rankBg:rm.bg, rankColor:rm.color}); });

    const kSuggestions = [
      '28tトレーラーで通行できる橋梁の確認方法は？',
      '狭隘道路の搬入で必要な現地確認項目を教えて',
      '学校周辺の搬入で配慮すべき時間帯と対策',
      '重機回送でトンネルの高さ制限はどう確認する？'
    ].map(q=>({ q, onClick:()=>this.quickSearch(q) }));
    const kSources = [
      {n:1,name:'国土交通省 xROAD',rank:'B'},{n:2,name:'国土数値情報',rank:'B'},{n:3,name:'OpenStreetMap',rank:'C'},{n:4,name:'社内 通行実績DB',rank:'D'}
    ].map(s=>{ const rm=this.rankMeta(s.rank); return Object.assign({}, s, {rankBg:rm.bg, rankColor:rm.color}); });
    const kRelatedProjects = [
      {id:'PRJ-2411',name:'ボックスカルバート搬入',sim:'87%'},
      {id:'PRJ-2405',name:'クローラークレーン50t 回送',sim:'81%'}
    ];

    const sysToggle = (k,label,note)=>({ key:k, label, note, on:this.state.sys[k], onToggle:()=>this.toggleSys(k), trackBg:this.state.sys[k]?'#1f8a4c':'#cdd2d8', knobX:this.state.sys[k]?'19px':'2px' });
    const sysNotify = [ sysToggle('emailNotify','メール通知','要確認・評価完了時にメール送信'), sysToggle('weeklyDigest','週次ダイジェスト','担当案件の更新まとめを配信') ];
    const sysProc = [ sysToggle('autoEval','ルート生成後に自動評価','候補生成と同時にリスク評価を実行'), sysToggle('cacheReuse','公開データのキャッシュ再利用','取得済みデータを一定期間再利用') ];
    const sysDisplay = [ sysToggle('darkChrome','ダークUIテーマ','サイドバー・ヘッダーを暗色で表示') ];
    const sysSecurity = [ sysToggle('anonUsage','利用状況の匿名送信','改善のため匿名の操作統計を送信') ];
    const apiMeta = ({ untested:{label:'未テスト',color:'#7c828c',dot:'#c4bfb4'}, testing:{label:'テスト中…',color:'#2b6cb0',dot:'#2b6cb0'}, ok:{label:'接続成功',color:'#1f8a4c',dot:'#1f8a4c'}, fail:{label:'接続失敗 — キーを確認してください',color:'#c0271f',dot:'#c0271f'} })[this.state.apiStatus] || {label:'未テスト',color:'#7c828c',dot:'#c4bfb4'};

    const projects = this.projects.map(p=>{
      const sm = this.statusMeta(p.status);
      return Object.assign({}, p, {
        sLabel:sm.label, sBg:sm.bg, sColor:sm.color, sBorder:sm.border,
        confirmColor: p.confirm>0 ? '#d9531e' : '#bdb8ad',
        onClick: ()=>this.selectProject(p.id)
      });
    });
    const total = projects.length;
    const stats = [
      {label:'登録案件', value:String(total), unit:'件', note:'API から取得した案件数', color:'#2b6cb0'},
      {label:'追加確認中', value:String(projects.filter(p=>p.status==='review_required').length), unit:'件', note:'レビュー依頼済みの案件', color:'#d9531e'},
      {label:'評価中', value:String(projects.filter(p=>p.status==='evaluating').length), unit:'件', note:'ルート生成・評価処理中', color:'#c47a00'},
      {label:'確認済み', value:String(projects.filter(p=>p.status==='reviewed').length), unit:'件', note:'承認済みの案件', color:'#1f8a4c'}
    ];
    const dataSources = this.dataSources.map(d=>{
      const ss = this.srcStatusMeta(d.status);
      const rm = this.rankMeta(d.rank);
      return Object.assign({}, d, {
        statusLabel:ss.label, statusColor:ss.color, dotColor:ss.color, dotHalo:this.hexToRgba(ss.color,0.18),
        rankLabel:d.rank, rankBg:rm.bg, rankColor:rm.color
      });
    });
    const knowledgePoints = this.knowledgePoints.map(k=>{
      const tm = this.typeMeta(k.type); const rm = this.rankMeta(k.rank);
      return Object.assign({}, k, { k:tm.k, color:tm.color, rankLabel:k.rank, rankBg:rm.bg, rankColor:rm.color });
    });
    const maxN = Math.max.apply(null, this.hazardBreakdown.map(h=>h.n));
    const hazardBreakdown = this.hazardBreakdown.map(h=>{
      const tm = this.typeMeta(h.type);
      return Object.assign({}, h, { color:tm.color, pct: Math.round(h.n/maxN*100)+'%' });
    });

    const lev = (l)=>this.levelMeta(l);
    const routes = this.routesData.map(r=>{
      const lm = lev(r.level);
      const sel = r.id===this.state.activeRouteId;
      const sc = r.score>=60?'#d9531e':r.score>=40?'#c47a00':'#1f8a4c';
      return Object.assign({}, r, {
        lvLabel:lm.label, lvColor:lm.color, lvBg:lm.bg, lvBorder:lm.border,
        selected:sel, onSelect:()=>this.selectRoute(r.id),
        cardBg: sel?'#ffffff':'#fbfaf6', cardBorder: sel?accent:'#ddd9d0', cardBar: sel?accent:'#e7e2d8',
        chipBg: sel?accent:'#ffffff', chipFg: sel?'#ffffff':'#5e646c', chipBorder: sel?accent:'#d4cfc4',
        scoreColor:sc
      });
    });
    const active = routes.find(r=>r.selected) || routes[0];

    const routeRender = [];
    routes.filter(r=>!r.selected).forEach(r=>routeRender.push({ d:r.d, css:'fill:none; stroke:#8d96a1; stroke-width:3.5; stroke-dasharray:2 8; stroke-linecap:round; stroke-linejoin:round; opacity:0.8;' }));
    if(active){
      routeRender.push({ d:active.d, css:'fill:none; stroke:#ffffff; stroke-width:11; stroke-linecap:round; stroke-linejoin:round;' });
      routeRender.push({ d:active.d, css:'fill:none; stroke:#1559b8; stroke-width:6; stroke-linecap:round; stroke-linejoin:round;' });
    }

    const rawH = this.hazardsByRoute[active.id] || [];
    const layers = this.state.layers;
    const layerCounts = {bridge:0,school:0,narrow:0,traffic:0,disaster:0,data:0};
    rawH.forEach(h=>{ layerCounts[this.layerGroup(h.type)]++; });
    const visibleHazards = rawH.filter(h=>layers[this.layerGroup(h.type)]).map(h=>{
      const tm = this.typeMeta(h.type); const lm = lev(h.level);
      const isSel = h.id===this.state.selectedHazardId;
      return Object.assign({}, h, { k:tm.k, pinColor:lm.color, isSel,
        transform:'translate('+h.x+','+h.y+') scale('+(isSel?1.18:1)+')', onClick:()=>this.selectHazard(h.id) });
    }).sort((a,b)=>(a.isSel?1:0)-(b.isSel?1:0));

    const riskOrder = {confirm_required:0, exclusion_candidate:1, caution:2, data_insufficient:3, candidate:4};
    const riskList = rawH.slice().sort((a,b)=>(riskOrder[a.level]-riskOrder[b.level])).map(h=>{
      const tm = this.typeMeta(h.type); const lm = lev(h.level);
      const st = this.state.hazardStatus[h.id]||h.status; const sm = this.hzStatusMeta(st);
      return Object.assign({}, h, { k:tm.k, typeLabel:tm.label, pinColor:lm.color,
        lvLabel:lm.label, lvColor:lm.color, lvBg:lm.bg, lvBorder:lm.border,
        isSel:h.id===this.state.selectedHazardId, onClick:()=>this.selectHazard(h.id),
        stLabel:sm.label, stColor:sm.color,
        rowBg: h.id===this.state.selectedHazardId?'#fff6ee':'#ffffff' });
    });

    const activeBreak = active.breakdown.map(b=>{
      const ratio = b.v/b.m;
      const c = ratio>=0.8?'#d9531e':ratio>=0.5?'#c47a00':'#1f8a4c';
      return { label:b.label, v:b.v, m:b.m, pct:Math.round(ratio*100)+'%', color:c };
    });
    const aLM = lev(active.level);
    const layerPanel = [
      {key:'bridge',label:'橋梁・トンネル',color:'#d9531e'},
      {key:'school',label:'学校・病院',color:'#c47a00'},
      {key:'narrow',label:'狭隘道路',color:'#c47a00'},
      {key:'traffic',label:'交通量',color:'#2b6cb0'},
      {key:'disaster',label:'災害リスク',color:'#7b5ea7'},
      {key:'data',label:'データ不足',color:'#5a6573'}
    ].map(l=>({ key:l.key, label:l.label, count:layerCounts[l.key], on:layers[l.key],
      onToggle:()=>this.toggleLayer(l.key),
      boxBg: layers[l.key]?l.color:'#ffffff', boxBorder:l.color, check: layers[l.key]?'✓':'',
      rowColor: layers[l.key]?'#1f2329':'#9aa0a7' }));

    let hazard = null; const showHazard = !!this.state.selectedHazardId;
    if(showHazard){
      const h = rawH.find(x=>x.id===this.state.selectedHazardId);
      if(h){
        const tm=this.typeMeta(h.type); const lm=lev(h.level); const rm=this.rankMeta(h.rank);
        const cur = this.state.hazardStatus[h.id]||h.status;
        const [hLat, hLng] = this._geo(h.x, h.y);
        const statusKeys = h.api
          ? ['unconfirmed','confirmed','needs_review','not_applicable']
          : ['unconfirmed','checking','confirmed_ok','confirmed_ng','not_applicable'];
        const statusOptions = statusKeys.map(key=>{
          const sm=this.hzStatusMeta(key); const on=cur===key;
          return { key, label:sm.label, on,
            onClick: h.api ? ()=>this.confirmRisk(h.routeId, h.id, key) : ()=>this.setHazardStatus(h.id,key),
            bg: on?sm.color:'#ffffff', fg: on?'#ffffff':'#5e646c', border: on?sm.color:'#d4cfc4' };
        });
        hazard = Object.assign({}, h, { k:tm.k, typeLabel:tm.label, pinColor:lm.color,
          lvLabel:lm.label, lvColor:lm.color, lvBg:lm.bg, lvBorder:lm.border,
          rankLabel:h.rank, rankBg:rm.bg, rankColor:rm.color,
          coords:hLat.toFixed(5)+'°N, '+hLng.toFixed(5)+'°E',
          routeName:active.name, statusOptions });
      }
    }

    const chip = (on)=>({ bg: on?accent:'#ffffff', fg: on?'#ffffff':'#5e646c', border: on?accent:'#d4cfc4' });
    const vehicleTypes = [
      {key:'normal',label:'普通貨物'},{key:'large',label:'大型貨物'},{key:'trailer',label:'トレーラー'},{key:'heavy',label:'重機回送'},{key:'special',label:'特殊車両'}
    ].map(v=>{ const on=this.state.vehicleType===v.key; const c=chip(on); return Object.assign({}, v, c, {on, onClick:()=>this.setVehicleType(v.key)}); });
    const clientTypes = [{key:'public',label:'公共'},{key:'private',label:'民間'},{key:'other',label:'その他'}].map(v=>{ const on=this.state.clientType===v.key; const c=chip(on); return Object.assign({}, v, c, {on, onClick:()=>this.setClientType(v.key)}); });
    const timeWindows = [
      {key:'daytime',label:'日中 9-17時'},
      {key:'morning_peak',label:'朝ピーク 7-9時'},
      {key:'evening_peak',label:'夕方 17-19時'},
      {key:'night',label:'夜間 22-5時'}
    ].map(v=>{ const on=this.state.timeWindow===v.key; const c=chip(on); return Object.assign({}, v, c, {on, onClick:()=>this.setTimeWindow(v.key)}); });
    const avoidList = [
      {key:'school',label:'学校・通学路周辺'},{key:'residential',label:'住宅密集地'},{key:'narrow',label:'狭隘道路'},{key:'crossing',label:'踏切'},{key:'slope',label:'急勾配'}
    ].map(a=>{ const on=this.state.avoid[a.key]; return Object.assign({}, a, {on, onToggle:()=>this.toggleAvoid(a.key), boxBg:on?accent:'#fff', boxBorder:on?accent:'#c4bfb4', check:on?'✓':'', labelColor:on?'#1f2329':'#5e646c'}); });
    const vtLabel = (vehicleTypes.find(v=>v.on)||{}).label || '—';
    const night = this.state.nightAllowed;

    const checklistDefs = [
      {key:'road_admin', label:'道路管理者へ橋梁の耐荷重・通行可否を確認', tag:'道路管理者'},
      {key:'tunnel_h', label:'トンネル・アンダーパスの制限高さを確認', tag:'現地確認'},
      {key:'police', label:'警察へ交差点・交通誘導を協議（道路使用許可）', tag:'警察'},
      {key:'width', label:'狭隘区間の有効幅員・待避所を現地確認', tag:'現地確認'},
      {key:'school_time', label:'学校の登下校時間帯を回避する搬入計画を作成', tag:'計画'},
      {key:'weather', label:'搬入日の気象・河川水位を確認し代替日を準備', tag:'運用'},
      {key:'partner', label:'協力会社へ過去通行実績・誘導員手配を確認', tag:'協力会社'}
    ];
    const checklist = checklistDefs.map(c=>{ const on=!!this.state.checks[c.key]; return Object.assign({}, c, { on, onToggle:()=>this.toggleCheck(c.key), boxBg:on?'#1f8a4c':'#fff', boxBorder:on?'#1f8a4c':'#c4bfb4', check:on?'✓':'', labelColor:on?'#9aa0a7':'#3a3f46', deco:on?'line-through':'none' }); });
    const checkedCount = checklist.filter(c=>c.on).length;
    const confirmTargets = [
      {label:'道路管理者（国・県・市）', note:'橋梁耐荷重・通行可否・道路占用'},
      {label:'警察署 交通課', note:'道路使用許可・交通誘導協議'},
      {label:'協力会社・運送会社', note:'通行実績・誘導員・待機/転回場所'},
      {label:'発注者', note:'施工計画・搬入計画の合意'}
    ];
    const memoRoutes = routes.map(r=>({ letter:r.letter, name:r.name, distance:r.distance, duration:r.duration, lvLabel:r.lvLabel, lvColor:r.lvColor, lvBg:r.lvBg, confirm:r.counts.confirm, data:r.counts.data, isActive:r.selected }));
    const memoHazards = riskList.slice(0,6).map((h,i)=>({ no:i+1, typeLabel:h.typeLabel, name:h.name, lvLabel:h.lvLabel, lvColor:h.lvColor, source:h.source, rank:h.rank }));

    const mdText = '# 搬入ルート初期検討メモ\n\n## 1. 案件概要\n- 工事件名: 第二期 護岸ブロック据付工事\n- 現場名: △△川 右岸 2.4k 付近\n- 担当者: 中村 健三（施工計画担当）\n- 作成日: 2026/06/19\n\n## 2. 搬入条件\n- 出発地: ◇◇生コン 第二プラント\n- 到着地: △△川 右岸 2.4k 付近\n- 車両種別: トレーラー\n- 全高: 3.8 m ／ 総重量: 28.0 t\n- 搬入時間帯: 日中 9-17時（夜間不可）\n\n## 3. ルート候補比較\n| 候補 | 距離(km) | 時間(分) | 評価 | 要確認 | 不足 |\n|---|---:|---:|---|---:|---:|\n| A 距離優先 | 12.4 | 34 | 要確認 | 2 | 1 |\n| B 幹線優先 | 15.1 | 38 | 注意 | 1 | 1 |\n| C 住宅地回避 | 17.2 | 46 | 利用候補 | 0 | 2 |\n| D 構造物確認 | 14.0 | 41 | 要確認 | 4 | 1 |\n\n## 4. 主な注意箇所（候補A）\n| No | 種別 | 場所 | 判定 | 出典 |\n|---:|---|---|---|---|\n| 1 | 橋梁 | 〇〇川 △△橋 | 要確認 | OSM (C) |\n| 2 | トンネル | △△トンネル | 要確認 | OSM (C) |\n| 3 | 学校 | ××小学校 | 注意 | 国土数値情報 (B) |\n\n## 5. 追加確認事項\n- 道路管理者へ「△△橋の耐荷重・通行可否」を確認（総重量 28.0t）\n- 「△△トンネルの制限高さ」を確認（全高 3.8m）\n- 狭隘区間（市道□□線）の有効幅員を現地確認\n\n## 6. 注意文\n本資料は公開データに基づく初期検討資料であり、通行可否を保証するものではありません。';
    const csvText = 'route_id,name,distance_km,duration_min,risk_level,confirm_required,data_insufficient\nA,距離優先ルート,12.4,34,confirm_required,2,1\nB,幹線道路優先ルート,15.1,38,caution,1,1\nC,住宅地回避ルート,17.2,46,candidate,0,2\nD,橋梁・トンネル確認重視,14.0,41,confirm_required,4,1';
    const reportCode = this.state.apiReport || (fmt==='csv'?csvText:mdText);
    const showCode = fmt==='markdown'||fmt==='csv';
    const isPdf = fmt==='pdf';
    const pidLabel = this.state.activeProjectId ? String(this.state.activeProjectId).slice(0,12) : 'NEW';
    const reportFileName = fmt==='csv' ? 'route_comparison_'+pidLabel+'.csv' : (fmt==='pdf' ? 'route-report-'+pidLabel+'.pdf' : 'risk_memo_'+pidLabel+'.md');

    const adminSources = this.dataSources.map(d=>{ const ss=this.srcStatusMeta(d.status); const rm=this.rankMeta(d.rank); const en=d.status!=='down'; return { name:d.name, statusLabel:ss.label, statusColor:ss.color, dotColor:ss.color, rankLabel:d.rank, rankBg:rm.bg, rankColor:rm.color, freq:d.freq, checked:d.checked, toggleBg: en?'#1f8a4c':'#cdd2d8', toggleX: en?'19px':'2px' }; });
    const evalWeights = [ {label:'橋梁・トンネル・高さ重量', w:25}, {label:'道路条件・狭隘性', w:20}, {label:'交通量・混雑', w:15}, {label:'周辺施設・近隣影響', w:15}, {label:'災害・地形リスク', w:10}, {label:'データ不足', w:10}, {label:'運用面', w:5} ].map(e=>Object.assign({}, e, {pct:(e.w/25*100)+'%'}));
    const evalRules = [ {id:'RR-BRIDGE-001', cond:'橋梁あり ＋ 重量制限情報なし', lvl:'要確認', lc:'#d9531e'}, {id:'RR-TUNNEL-001', cond:'トンネル/アンダーパス ＋ 高さ情報なし', lvl:'要確認', lc:'#d9531e'}, {id:'RR-SCHOOL-001', cond:'学校300m以内 ＋ 朝夕搬入', lvl:'注意', lc:'#c47a00'}, {id:'RR-RESIDENTIAL-001', cond:'住宅地通過比率が閾値以上', lvl:'注意', lc:'#c47a00'}, {id:'RR-OSM-QUALITY-001', cond:'OSM属性欠損が多い', lvl:'データ不足', lc:'#5a6573'} ];
    const adminRoles = [ {role:'admin', label:'管理者', perms:'全機能・データソース・評価ルール・ユーザー管理'}, {role:'dx_operator', label:'IT/DX', perms:'接続状況・ログ確認・設定変更'}, {role:'planner', label:'施工計画', perms:'案件作成・評価・レポート出力'}, {role:'site_user', label:'現場', perms:'閲覧・コメント・確認結果登録'}, {role:'viewer', label:'閲覧', perms:'ルート候補とレポートの閲覧'} ];
    const adminLogs = this.state.apiAuditLogs || [ {t:'06/19 06:12', u:'system', a:'JOB-001 データソース接続確認', tg:'5 sources'}, {t:'06/18 14:35', u:'中村 健三', a:'確認ステータス更新', tg:'risk A5'}, {t:'06/18 14:20', u:'中村 健三', a:'リスクメモ生成', tg:'PRJ-2418'}, {t:'06/18 09:02', u:'佐藤（DX）', a:'評価ルール変更 RR-BRIDGE-001', tg:'score 20→25'}, {t:'06/17 02:00', u:'system', a:'JOB-002 国土数値情報取込', tg:'対象エリア'} ];

    const activeProject = (this.state.apiProjects || []).find(p=>p.id===this.state.activeProjectId) || null;
    const activeProjectName = activeProject ? activeProject.name : '案件未選択';
    const activeStatusMeta = activeProject ? this.statusMeta(activeProject.status) : this.statusMeta('draft');
    const todayLabel = new Date().toLocaleDateString('ja-JP',{year:'numeric',month:'2-digit',day:'2-digit',weekday:'short'}) + ' ' + new Date().toLocaleTimeString('ja-JP',{hour:'2-digit',minute:'2-digit'});
    const userLabel = this.state.apiKey ? 'APIキー運用者' : '未ログイン（PoC）';
    const activeProjectLabel = activeProject ? activeProject.name : '案件未選択';
    const activeProjectIdLabel = this.state.activeProjectId || '—';

    const pf = this.state.projectForm;
    const pfFields = {
      project_name: { value: pf.project_name, onInput: (e)=>this.setProjectFormField('project_name', e.target.value) },
      site_name: { value: pf.site_name, onInput: (e)=>this.setProjectFormField('site_name', e.target.value) },
      planner: { value: pf.planner, onInput: (e)=>this.setProjectFormField('planner', e.target.value) },
      start_name: { value: pf.start_name, onInput: (e)=>this.setProjectFormField('start_name', e.target.value) },
      start_lat: { value: pf.start_lat, onInput: (e)=>this.setProjectFormField('start_lat', e.target.value) },
      start_lng: { value: pf.start_lng, onInput: (e)=>this.setProjectFormField('start_lng', e.target.value) },
      dest_name: { value: pf.dest_name, onInput: (e)=>this.setProjectFormField('dest_name', e.target.value) },
      dest_lat: { value: pf.dest_lat, onInput: (e)=>this.setProjectFormField('dest_lat', e.target.value) },
      dest_lng: { value: pf.dest_lng, onInput: (e)=>this.setProjectFormField('dest_lng', e.target.value) },
      length_m: { value: pf.length_m, onInput: (e)=>this.setProjectFormField('length_m', e.target.value) },
      width_m: { value: pf.width_m, onInput: (e)=>this.setProjectFormField('width_m', e.target.value) },
      height_m: { value: pf.height_m, onInput: (e)=>this.setProjectFormField('height_m', e.target.value) },
      gross_weight_t: { value: pf.gross_weight_t, onInput: (e)=>this.setProjectFormField('gross_weight_t', e.target.value) },
      axle_weight_t: { value: pf.axle_weight_t, onInput: (e)=>this.setProjectFormField('axle_weight_t', e.target.value) },
      cargo_type: { value: pf.cargo_type, onInput: (e)=>this.setProjectFormField('cargo_type', e.target.value) },
      delivery_date: { value: pf.delivery_date, onInput: (e)=>this.setProjectFormField('delivery_date', e.target.value) },
      notes: { value: pf.notes, onInput: (e)=>this.setProjectFormField('notes', e.target.value) }
    };
    const specialToggle = {
      on: !!pf.special_vehicle,
      onToggle: ()=>this.setProjectFormField('special_vehicle', !pf.special_vehicle),
      boxBg: pf.special_vehicle ? accent : '#fff',
      boxBorder: pf.special_vehicle ? accent : '#c4bfb4',
      check: pf.special_vehicle ? '✓' : '',
      labelColor: pf.special_vehicle ? '#1f2329' : '#5e646c'
    };
    const genRoutesLabel = this.state.apiLoading ? '処理中…' : '案件を登録してルート候補を生成';
    const summaryProjectName = pf.project_name || '（未入力）';
    const summaryRoute = (pf.start_name || '出発地') + ' → ' + (pf.dest_name || '到着地');
    const summaryVehicle = (pf.height_m || '未入力') + 'm / ' + (pf.gross_weight_t || '未入力') + 't';

    const fmt = this.state.reportFormat;
    const reportFormats = [{key:'markdown',label:'Markdown'},{key:'csv',label:'CSV'},{key:'pdf',label:'PDF'}].map(f=>{
      const on=this.state.reportFormat===f.key;
      return Object.assign({}, f, {on, onClick:()=>this.setReportFormatWithFetch(f.key),
        bg:on?'#1a1d21':'#fff', fg:on?'#fff':'#5e646c', border:on?'#1a1d21':'#d4cfc4'});
    });

    return {
      accent, screen,
      isDashboard: screen==='dashboard', isProject: screen==='project', isRoutes: screen==='routes',
      isMemo: screen==='memo', isReport: screen==='report', isAdmin: screen==='admin',
      isKnowledge: screen==='knowledge', isFacilities: screen==='facilities', isSystem: screen==='system',
      nav: { dashboard:mk('dashboard'), project:mk('project'), routes:mk('routes'), memo:mk('memo'), report:mk('report'), admin:mk('admin'), knowledge:mk('knowledge'), facilities:mk('facilities'), system:mk('system') },
      stats, projects, dataSources, knowledgePoints, hazardBreakdown,
      pidLabel, activeProjectName, activeStatusLabel: activeStatusMeta.label, todayLabel, userLabel,
      newProject: ()=>this.setScreen('project'),
      routes, active, routeRender, visibleHazards, riskList, activeBreak,
      activeScoreColor: active?active.scoreColor:'#c47a00', activeLvLabel: aLM.label, activeLvBg: aLM.bg, activeLvColor: aLM.color, activeLvBorder: aLM.border,
      layerPanel, showHazard, showRouteSummary: !showHazard, hazard,
      goReport: ()=>this.setScreen('report'), goMemo: ()=>this.setScreen('memo'),
      closeHazardBtn: ()=>this.closeHazard(),
      vehicleTypes, clientTypes, timeWindows, avoidList, vtLabel, night,
      nightToggle: ()=>this.toggleNight(),
      specialToggle,
      genRoutes: ()=>this.saveAndGenerate(),
      genRoutesLabel,
      summaryProjectName, summaryRoute, summaryVehicle,
      saveAndGenerate: ()=>this.saveAndGenerate(),
      regenRoutes: ()=>this.regenRoutes(),
      submitProject: ()=>this.submitProject(),
      approveProject: ()=>this.approveProject(),
      refreshAdmin: ()=>{ this.fetchDataSources(); this.fetchAuditLogs(); },
      checklist, checkedCount, checkTotal: checklist.length, confirmTargets, memoRoutes, memoHazards,
      reportFormats, reportCode, showCode, showRendered: !showCode && !isPdf, isPdf, reportFileName,
      adminSources, evalWeights, evalRules, adminRoles, adminLogs,
      facCats, facilities, facCount: facilities.length,
      kQuery: this.state.kQuery, kSearching: this.state.kSearching, kHasResult: this.state.kHasResult, kAnswer: this.state.kAnswer, kError: this.state.kError,
      kShowAnswer: this.state.kHasResult && !this.state.kSearching && !this.state.kError,
      kInitial: !this.state.kHasResult,
      kSuggestions, kSources, kRelatedProjects,
      onKInput: (e)=>this.setState({ kQuery:e.target.value }),
      onKKey: (e)=>{ if(e.key==='Enter') this.runKnowledgeSearch(); },
      runKSearch: ()=>this.runKnowledgeSearch(),
      sysNotify, sysProc, sysDisplay, sysSecurity,
      apiKey: this.state.apiKey, apiStatusLabel: apiMeta.label, apiStatusColor: apiMeta.color, apiStatusDot: apiMeta.dot,
      apiTesting: this.state.apiStatus==='testing', apiSaved: this.state.apiSaved,
      onApiInput: (e)=>this.setApiKey(e.target.value), testApi: ()=>this.testApi(), saveApi: ()=>this.saveApi(),
      apiLoading: this.state.apiLoading, apiError: this.state.apiError, apiNotice: this.state.apiNotice, apiOnline: this.state.apiOnline,
      activeProjectLabel, activeProjectIdLabel,
      downloadReport: ()=>this.downloadReport(this.state.reportFormat),
      riskConfirming: this.state.riskConfirming, riskConfirmBtnLabel: this.state.riskConfirming ? '登録中…' : '登録',
      onRiskComment: (e)=>this.setRiskComment(e.target.value),
      submitRiskComment: ()=>this.submitRiskComment(),
      pfFields, createProject: ()=>this.createProject(),
      fetchProjects: ()=>this.fetchProjects()
    };
  }
}
