const $ = (selector, root = document) => root.querySelector(selector);
const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const iconPaths = {
  home:'<path d="m3 10 7-6 7 6v7H3Z"/><path d="M8 17v-5h4v5"/>',
  layers:'<path d="m2 6 8-4 8 4-8 4Z"/><path d="m2 10 8 4 8-4M2 14l8 4 8-4"/>',
  book:'<path d="M10 4C7 2 4 2 2 3v13c3-1 5-1 8 1 3-2 5-2 8-1V3c-2-1-5-1-8 1Z"/><path d="M10 4v13"/>',
  code:'<path d="m6 5-4 5 4 5m8-10 4 5-4 5M12 3 8 17"/>',
  terminal:'<rect x="2" y="3" width="16" height="14" rx="2"/><path d="m5 7 3 3-3 3m5 0h5"/>',
  network:'<circle cx="10" cy="4" r="2"/><circle cx="4" cy="16" r="2"/><circle cx="16" cy="16" r="2"/><path d="M10 6v4H4v4m6-4h6v4"/>',
  spark:'<path d="m10 2 2 6 6 2-6 2-2 6-2-6-6-2 6-2Z"/>',
  shield:'<path d="m10 2 7 3v5c0 4-7 8-7 8S3 14 3 10V5Z"/><path d="m6 10 3 3 5-6"/>',
  repeat:'<path d="M4 7a7 7 0 0 1 12-2l2 3m0-5v5h-5M16 13A7 7 0 0 1 4 15l-2-3m0 5v-5h5"/>',
  history:'<circle cx="10" cy="10" r="7"/><path d="M10 6v4l3 2"/>',
  chart:'<path d="M3 3v14h15M7 13V9m4 4V5m4 8V7"/>',
  settings:'<path d="M3 5h14M3 10h14M3 15h14"/><circle cx="7" cy="5" r="2" fill="currentColor"/><circle cx="13" cy="10" r="2" fill="currentColor"/><circle cx="8" cy="15" r="2" fill="currentColor"/>',
  arrow:'<path d="M3 10h14m-5-5 5 5-5 5"/>',
  check:'<path d="m4 10 4 4 8-9"/>',
  clock:'<circle cx="10" cy="10" r="7"/><path d="M10 5v5l3 2"/>',
  alert:'<path d="m10 2 8 15H2Z"/><path d="M10 7v4m0 3v.1"/>',
  search:'<circle cx="8" cy="8" r="5"/><path d="m12 12 6 6"/>',
};
const icon = name => `<svg class="icon" viewBox="0 0 20 20" aria-hidden="true">${iconPaths[name] || iconPaths.book}</svg>`;
const nav = [
  ['dashboard','学习概览','home'], ['courses','学习路线','layers'], ['problems','题目训练','code'],
  ['diagnose','诊断工作台','spark'], ['projects','项目工坊','terminal'], ['knowledge','知识资料库','book'],
  ['reviews','错题与复习','repeat'], ['runs','运行记录','history'],
  ['insights','学习统计','chart'], ['settings','空间设置','settings'],
];
let learner = localStorage.getItem('verdictpilot.learner');
if (!learner) { learner = 'learner_' + crypto.randomUUID().replaceAll('-',''); localStorage.setItem('verdictpilot.learner', learner); }
const state = {learner, health:null, catalog:null, problemIndex:null, lesson:null, problem:null, routeToken:0, runOffset:0, tag:'全部', difficulty:'全部', problemSearch:'', currentRun:null};
let toastTimer, noteTimer, draftTimer;
const main = $('#main');
function toast(message, error = false) {
  const node = $('#toast'); node.textContent = message; node.className = 'toast' + (error ? ' error' : ''); node.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => node.hidden = true, 3800);
}
async function api(path, options = {}) {
  const url = new URL(path, location.origin); url.searchParams.set('learner_id', state.learner);
  const response = await fetch(url, {headers:{'Content-Type':'application/json'}, ...options});
  const data = await response.json();
  if (!response.ok) {
    const detail = data.detail;
    throw new Error(Array.isArray(detail) ? detail.map(v => `${v.loc?.at(-1) || ''}: ${v.msg}`).join('；') : detail || `请求失败（${response.status}）`);
  }
  return data;
}
const post = (path, data) => api(path,{method:'POST',body:JSON.stringify(data)});
const put = (path, data) => api(path,{method:'PUT',body:JSON.stringify(data)});
const shortDate = value => new Date(value).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'});
const dayDate = value => new Date(value).toLocaleDateString('zh-CN',{timeZone:'Asia/Shanghai',month:'long',day:'numeric'});
const verdictNames = {passed:'测试通过',wrong_answer:'答案错误',compile_error:'编译错误',runtime_error:'运行错误',time_limit:'运行超时',output_limit:'输出超限',disabled:'未开启执行',internal_error:'执行异常',queued:'等待执行',running:'运行中',failed:'任务失败',interrupted:'已中断',completed:'诊断完成'};
function badge(verdict) {
  const color = verdict==='passed' ? 'green' : ['wrong_answer','compile_error','runtime_error','time_limit','output_limit','failed','internal_error'].includes(verdict) ? 'red' : ['running','queued'].includes(verdict) ? 'blue' : '';
  return `<span class="badge ${color}">${escape(verdictNames[verdict] || verdict)}</span>`;
}
function markdown(value) {
  const lines = String(value || '').split('\n'); let html='', code=false, buffer=[], list=false;
  const inline = text => escape(text).replace(/`([^`]+)`/g,'<code>$1</code>').replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>');
  const closeList=()=>{if(list){html+='</ul>';list=false;}};
  for (const line of lines) {
    if (line.startsWith('```')) { closeList(); if(code){html+=`<pre><code>${escape(buffer.join('\n'))}</code></pre>`;buffer=[];} code=!code;continue; }
    if(code){buffer.push(line);continue;}
    const heading=line.match(/^(#{1,3})\s+(.*)$/);
    if(heading){closeList();const level=Math.min(3,heading[1].length+1);html+=`<h${level}>${inline(heading[2])}</h${level}>`;continue;}
    if(/^\s*[-*]\s/.test(line)||/^\d+\.\s/.test(line)){if(!list){html+='<ul>';list=true;}html+=`<li>${inline(line.replace(/^\s*[-*]\s|^\d+\.\s/,''))}</li>`;continue;}
    closeList(); if(line.trim())html+=`<p>${inline(line)}</p>`;
  }
  closeList(); if(code)html+=`<pre><code>${escape(buffer.join('\n'))}</code></pre>`;return html;
}
function heading(title,subtitle,eyebrow,action='') {
  return `<div class="page-heading"><div><div class="eyebrow">${escape(eyebrow)}</div><h1>${escape(title)}</h1><p>${escape(subtitle)}</p></div>${action}</div>`;
}
function empty(title,description,action='',compact=false) {
  return `<div class="empty-state ${compact?'compact':''}">${icon('layers')}<h3>${escape(title)}</h3><p>${escape(description)}</p>${action}</div>`;
}
function activityChart(items) {
  const max=Math.max(1,...items.map(x=>x.count));
  return `<div class="activity-bars">${items.map(x=>`<div class="bar-col" data-label="${escape(x.date)} · ${x.count} 次"><div class="bar ${x.count?'':'empty'}" style="height:${x.count?Math.max(12,x.count/max*100):5}%"></div></div>`).join('')}</div><div class="activity-labels"><span>${items[0]?.date.slice(5)}</span><span>最近 14 天 · 测验与运行次数</span><span>今天</span></div>`;
}
function metricCards(data) {
  const m=data.metrics;
  const cards=[['测验通过',m.lessons_passed,`/ ${m.lessons_total} 节`,'book','成绩 ≥80%，实践任务另行自查'],['题目测试通过',m.problems_passed,`/ ${m.problems_total} 题`,'code','统计已通过本题库测试的题目'],['待复习错题',m.due_reviews,'题','repeat','依据下一次复习时间安排'],['连续学习',m.streak,'天','chart','测验或运行均计入学习活动']];
  return `<div class="metrics">${cards.map(c=>`<div class="metric"><div class="metric-label">${c[0]}${icon(c[3])}</div><div class="metric-value">${c[1]}<span>${c[2]}</span></div><div class="metric-sub">${c[4]}</div></div>`).join('')}</div>`;
}
function runTable(items) {
  if(!items.length)return empty('这里将留下你的实践记录','做一次题目提交或代码诊断，结果和执行证据会保存在这里。','<a class="button small" href="#lab/sum">开始第一次练习</a>',true);
  return `<div class="table-wrap"><table class="data-table"><thead><tr><th>任务</th><th>结果</th><th class="hide-mobile">耗时</th><th>时间</th><th></th></tr></thead><tbody>${items.map(r=>`<tr><td>${escape(r.title)}<div class="muted" style="font-size:9px">${r.kind==='submission'?'代码训练':'Agent 诊断'}</div></td><td>${badge(r.verdict||r.status)}</td><td class="hide-mobile">${r.elapsed_ms ? (r.elapsed_ms/1000).toFixed(2)+' s' : '—'}</td><td>${shortDate(r.created_at)}</td><td><a class="text-link" href="#run/${r.id}">详情 ↗</a></td></tr>`).join('')}</tbody></table></div>`;
}
async function dashboardView() {
  const data=await api('/v1/dashboard'); state.dashboard=data; updateProfile(data.profile);
  const next=data.recommendations[0]; const percent=Math.round(data.metrics.lessons_passed/data.metrics.lessons_total*100);
  return heading(`你好，${data.profile.display_name}。`,'从一个小任务开始，把今天的理解落实到代码。','YOUR LEARNING SPACE',`<span class="date-label">${new Date().toLocaleDateString('zh-CN',{timeZone:'Asia/Shanghai',month:'long',day:'numeric',weekday:'long'})}</span>`)+
  `<section class="hero"><div class="hero-copy"><div class="hero-label">LEARN · BUILD · VERIFY</div><h2>让每一次练习<br>都留下进步的证据。</h2><p>${next?`下一步 · ${escape(next.title)} · 约 ${next.minutes} 分钟`:'课程测验已完成，继续用真实练习检验自己的理解。'}</p><a class="button dark" href="${next?'#lesson/'+next.id:'#problems'}">${next?'继续学习':'进入题目训练'} ${icon('arrow')}</a></div><div class="hero-visual" aria-hidden="true"><div class="orbital"></div><span class="float-symbol">✳</span><div class="float-card"><div class="mini-label">LEARNING IN PROGRESS</div><h3>把知识，变成自己的能力</h3><div class="progress"><span style="width:${percent}%"></span></div><small>${data.metrics.lessons_passed} / ${data.metrics.lessons_total} 节测验通过</small></div><div class="float-token">&lt; learn. verify. repeat /&gt;</div></div></section>`+
  metricCards(data)+`<div class="dashboard-grid"><div><div class="section-heading"><h2>你的学习路线<small>6 条路线 · 从基础到交付</small></h2><a href="#courses" class="text-link">查看全部 ↗</a></div><div class="track-grid">${data.tracks.map((t,i)=>`<a class="track-card" href="#courses/${t.id}"><div class="track-top"><div class="track-icon ${t.color}">${icon(t.icon)}</div><span class="track-number">PATH / 0${i+1}</span></div><h3>${escape(t.title)}</h3><p>${escape(t.subtitle)}</p><div class="progress"><span style="width:${t.passed/t.total*100}%"></span></div><div class="track-meta"><span>${t.passed} / ${t.total} 节测验通过</span><span>开始探索 ↗</span></div></a>`).join('')}</div></div><div><section class="card"><div class="section-heading"><h2>今天的三个小步骤</h2><span class="badge">${data.profile.daily_minutes} MIN / DAY</span></div>${[
    [next?next.title:'继续挑战新题目',next?`理解核心概念 · ${next.minutes} 分钟`:'把已学方法用于新问题',next?'#lesson/'+next.id:'#problems','去学习'],
    ['用代码检验自己的理解','编译、测试、反例，留下可复查结果','#lab/sum','去训练'],
    [data.metrics.due_reviews?`${data.metrics.due_reviews} 道错题等待复习`:'把一次错误变成教训','先解释根因，再重写与复测','#reviews','去复盘'],
  ].map((t,i)=>`<div class="today-task"><span class="task-num">0${i+1}</span><div><h3>${escape(t[0])}</h3><p>${t[1]}</p><a class="text-link" href="${t[2]}">${t[3]} →</a></div></div>`).join('')}</section><section class="card"><div class="section-heading"><h2>学习节奏</h2><a class="text-link" href="#insights">统计 ↗</a></div>${activityChart(data.activity)}</section></div></div><section class="recent-section"><div class="section-heading"><h2>最近的实践<small>每次运行，都有迹可循</small></h2><a href="#runs" class="text-link">所有记录 ↗</a></div>${runTable(data.recent_runs)}</section>`;
}
const metricLabels={documents:'文档数',queries:'查询数',hit_at_3:'hit@3（0–1）',mrr:'MRR（0–1）',p95_ms:'P95 延迟（ms）',tests_passed:'通过测试数',generator_cases:'生成测试数',oracle_tests:'基线测试数',counterexamples:'反例数',reduction_ratio:'缩减比例（0–1）',tool_success_rate:'工具成功率（0–1）',cases:'评测样本数',diagnosis_accuracy:'诊断准确率（0–1）',repair_pass_rate:'修复通过率（0–1）',contract_tests:'契约测试数',recovery_tests:'恢复测试数',orphan_jobs:'遗留任务数',cleanup_tests:'资源清理测试数',requests:'请求数',rejection_rate:'拒绝率（0–1）',queue_p95_ms:'排队 P95（ms）',execution_p95_ms:'执行 P95（ms）',record_count:'运行记录数',trace_coverage:'轨迹覆盖率（0–1）',grader_tests:'评分器测试数',calibration_cases:'校准样本数',mean_cost:'平均单次费用（按报告币种）',reviewed_failures:'审阅失败数',regression_cases:'回归用例数'};
function evidenceForm(project,milestone) {
  const previous=state.projectData.evidence.find(e=>e.project_id===project.id&&e.milestone_id===milestone.id)||{};
  return `<form id="project-evidence-form" data-project="${project.id}" data-milestone="${milestone.id}"><p class="muted" style="margin-bottom:16px">${escape(milestone.evidence)}<br>只填写自己实际跑出的结果，比例指标用 0–1。</p><label class="form-field"><span>本次实现与发现</span><textarea name="summary" required minlength="10" maxlength="10000" placeholder="实现了什么，测试如何，失败在哪里…">${escape(previous.summary||'')}</textarea></label><label class="form-field"><span>可复现命令</span><input name="command" value="${escape(previous.command||'')}" required minlength="3" maxlength="2000" placeholder="例如：python eval.py --dataset queries-v1.jsonl"></label><label class="form-field"><span>报告路径 / 仓库版本 / 证据链接</span><input name="artifact" value="${escape(previous.artifact||'')}" required minlength="3" maxlength="1000" placeholder="reports/baseline.json · commit abc123"></label>${milestone.metrics.map(m=>`<label class="form-field"><span>${escape(metricLabels[m]||m)}</span><input name="metric_${m}" type="number" required min="0" step="any" value="${previous.metrics?.[m]??''}"></label>`).join('')}<button class="button primary" type="submit">保存里程碑证据 ${icon('check')}</button><p class="note-status">${previous.updated_at?'上次记录：'+shortDate(previous.updated_at):'这是个人实测记录，平台不会自动宣称结果已经独立验证。'}</p></form>`;
}
async function projectsView(id) {
  const data=await api('/v1/projects');state.projectData=data;
  if(!id) return heading('做出能被复现的作品。','四个工程项目，从当前平台出发，逐步补齐检索、验证、可靠性与评测能力。','PROJECT WORKSHOP')+`<div class="notice">${icon('terminal')}<div>这里记录的是你实际实现、运行和测量的里程碑证据。课程测验只是起点；项目需要独立代码、固定数据与可复现报告。</div></div><div class="review-grid">${data.items.map(p=>{const recorded=data.evidence.filter(e=>e.project_id===p.id).length;return `<a class="track-card" href="#projects/${p.id}"><div class="track-top"><span class="track-icon ${p.color}">${icon(p.icon)}</span><span class="track-number">${p.category}</span></div><h2 style="font-size:17px;margin-bottom:10px">${escape(p.title)}</h2><p style="font-size:12px;line-height:1.9">${escape(p.description)}</p><div class="tags"><span class="tag">建议 ${p.duration}</span><span class="tag">${p.milestones.length} 个里程碑</span></div><div class="progress"><span style="width:${recorded/p.milestones.length*100}%"></span></div><div class="track-meta"><span>${recorded} / ${p.milestones.length} 个里程碑已记录证据</span><span>查看实施计划 →</span></div></a>`;}).join('')}</div>`;
  const p=data.items.find(p=>p.id===id);if(!p)throw new Error('项目不存在');state.currentProject=p;
  const m=p.milestones.find(m=>m.id===state.selectedMilestone)||p.milestones[0];state.selectedMilestone=m.id;
  return heading(p.title,p.description,p.category,'<a href="#projects" class="button">← 项目工坊</a>')+`<div class="notice">${icon('network')}<div>${escape(p.architecture)}</div></div><div class="reading-layout"><article class="article"><div class="reading-content">${markdown(p.body)}</div><h2 class="stack-gap">实施里程碑</h2>${p.milestones.map((m,i)=>{const e=data.evidence.find(e=>e.project_id===p.id&&e.milestone_id===m.id);return `<section class="exercise-box"><div class="section-heading"><h3>0${i+1} · ${escape(m.title)}</h3><span class="badge ${e?'green':''}">${e?'已记录证据':'待实践'}</span></div><ol>${m.tasks.map(t=>`<li>${escape(t)}</li>`).join('')}</ol><p class="muted">交付：${escape(m.evidence)}</p>${e?`<p class="muted stack-gap">记录：${escape(e.summary)}<br><code>${escape(e.command)}</code><br>${escape(e.artifact)}</p>`:''}</section>`;}).join('')}</article><aside class="lesson-aside"><section class="card"><h3>记录一次真实的进展</h3><label class="form-field"><span>选择里程碑</span><select id="milestone-select">${p.milestones.map(x=>`<option value="${x.id}" ${x.id===m.id?'selected':''}>${escape(x.title)}</option>`).join('')}</select></label><div id="project-evidence-panel">${evidenceForm(p,m)}</div></section></aside></div>`;
}
async function coursesView(trackId) {
  const data=await api('/v1/catalog'); state.catalog=data;
  const passed=new Set(Object.keys(data.progress).filter(k=>(data.progress[k].best_score||0)>=80));
  return heading('一步步，构建完整的能力。','算法思维与 Agent 工程并行推进，每课都有推导、实践任务和测验。','LEARNING PATHS')+
  `<div class="filter-bar"><a class="filter-chip ${trackId?'':'active'}" href="#courses">全部路线</a>${data.tracks.map(t=>`<a class="filter-chip ${t.id===trackId?'active':''}" href="#courses/${t.id}">${escape(t.title)}</a>`).join('')}</div>`+
  data.tracks.filter(t=>!trackId||t.id===trackId).map((t,index)=>{
    const lessons=data.lessons.filter(l=>l.track_id===t.id);
    return `<section class="course-group"><div class="course-header"><span class="track-icon ${t.color}">${icon(t.icon)}</span><div><h2>${escape(t.title)}</h2><p>${escape(t.outcome)}</p></div><small>${lessons.filter(l=>passed.has(l.id)).length} / ${lessons.length} 节测验通过</small></div><div>${lessons.map((l,i)=>{
      const ready=l.prerequisites.every(k=>passed.has(k));
      return `<a class="lesson-row" href="#lesson/${l.id}"><span class="lesson-number">${String(index*4+i+1).padStart(2,'0')}</span><div><h3>${escape(l.title)}</h3><p>${escape(l.description)}</p></div><div class="lesson-meta"><span class="duration">${l.minutes} 分钟</span>${passed.has(l.id)?'<span class="badge green">测验通过</span>':ready?'<span class="badge blue">推荐学习</span>':'<span class="badge">有前置课程</span>'}<span>↗</span></div></a>`;
    }).join('')}</div></section>`;
  }).join('');
}
async function lessonView(id) {
  const lesson=await api('/v1/lessons/'+encodeURIComponent(id)); state.lesson=lesson;
  const progress=lesson.progress||{};
  return `<div class="page-heading"><a href="#courses/${lesson.track_id}" class="text-link">← 返回学习路线</a><span class="date-label">${lesson.minutes} 分钟 · ${lesson.level}</span></div><div class="reading-layout"><article class="article"><div class="article-header"><span class="badge blue">课程 / ${escape(lesson.track_id)}</span><h1>${escape(lesson.title)}</h1><p>${escape(lesson.description)}</p></div><div class="reading-content">${markdown(lesson.body)}</div><section class="exercise-box"><h3>${icon('terminal')} ${escape(lesson.exercise.title)}</h3><ol>${lesson.exercise.steps.map(s=>`<li>${escape(s)}</li>`).join('')}</ol><label><input id="exercise-done" type="checkbox" ${progress.exercise_done?'checked':''}>我已完成实践任务（自查记录，不计入测验成绩）</label></section><section class="quiz-section"><h2>检查一下你的理解</h2><p class="quiz-intro">${lesson.quiz.length} 道选择题，成绩达到 80% 记为测验通过。提交后查看逐题解析。</p><form id="quiz-form">${lesson.quiz.map((q,i)=>`<div class="quiz-question"><h3>${i+1}. ${escape(q.question)}</h3>${q.options.map((o,j)=>`<label class="quiz-option"><input type="radio" name="q${i}" value="${j}" required>${escape(o)}</label>`).join('')}</div>`).join('')}<div id="quiz-feedback"></div><button type="submit" class="button primary">提交测验 ${icon('arrow')}</button></form></section></article><aside class="lesson-aside"><section class="card"><h3>这一课的学习闭环</h3><div class="aside-step">${icon('book')}阅读推导与实现</div><div class="aside-step">${icon('code')}完成实践任务</div><div class="aside-step">${icon('check')}提交测验并看解析</div><div class="setting-value"><span>最佳成绩</span><strong id="best-score">${progress.best_score??'—'}${progress.best_score!=null?' 分':''}</strong></div>${lesson.prerequisites.length?`<p class="muted stack-gap">建议先学</p>${lesson.prerequisites.map(p=>`<a class="document-link" href="#lesson/${p}"><strong>${escape(state.catalog?.lessons.find(l=>l.id===p)?.title||p)} →</strong></a>`).join('')}`:'<p class="muted stack-gap">这是一节起点课程，可以直接开始。</p>'}${lesson.related_problem?`<a class="button primary stack-gap" href="#lab/${lesson.related_problem}">练习关联题目 ${icon('arrow')}</a>`:''}</section><section class="card"><h3>写给未来自己的笔记</h3><textarea class="note-text" id="lesson-note" placeholder="用自己的话说明状态、不变量或设计取舍…">${escape(progress.note||'')}</textarea><div class="note-status" id="note-status">${progress.updated_at?'已保存 · '+shortDate(progress.updated_at):'输入后自动保存到本地数据库'}</div><button class="button small stack-gap" data-action="save-note">保存笔记</button></section></aside></div>`;
}
function problemCards() {
  const data=state.problemIndex;
  const items=data.items.filter(p=>(state.tag==='全部'||p.tags.includes(state.tag))&&(state.difficulty==='全部'||p.difficulty===state.difficulty)&&(!state.problemSearch||(p.title+' '+p.tags.join(' ')).toLowerCase().includes(state.problemSearch.toLowerCase())));
  return items.length?items.map(p=>{
    const progress=data.progress[p.id];
    return `<article class="problem-card"><div class="track-top"><span class="badge ${p.difficulty==='进阶'?'orange':p.difficulty==='中等'?'blue':'green'}">${p.difficulty}</span><span class="track-number">${escape(p.id)}</span></div><h3>${escape(p.title)}</h3><p>${escape(p.description)}</p><div class="tags">${p.tags.map(t=>`<span class="tag">${escape(t)}</span>`).join('')}</div><div class="problem-bottom"><small>${progress?.passed?'✓ 题库测试通过':progress?`${progress.attempts} 次提交`:'等待第一次练习'}</small><a href="#lab/${p.id}" class="text-link">开始训练 →</a></div></article>`;
  }).join(''):empty('没有匹配的题目','试试其他关键词或清除标签筛选。');
}
async function problemsView() {
  state.problemIndex=await api('/v1/problems');
  const tags=['全部',...new Set(state.problemIndex.items.flatMap(p=>p.tags))];
  return heading('把理解，落实到代码。','题面、分层提示、代码草稿与固定测试，组成一次完整训练。','PRACTICE LIBRARY','<a class="button" href="#diagnose">诊断自己的题目 ↗</a>')+`<div class="filter-bar"><input class="filter-input" id="problem-search" placeholder="搜索题目或算法…" value="${escape(state.problemSearch)}"><select id="difficulty-filter" aria-label="难度筛选">${['全部','入门','基础','中等','进阶'].map(d=>`<option ${d===state.difficulty?'selected':''}>${d}</option>`).join('')}</select></div><div class="filter-bar">${tags.map(t=>`<button class="filter-chip ${t===state.tag?'active':''}" data-action="filter-tag" data-tag="${escape(t)}">${escape(t)}</button>`).join('')}</div><div id="problem-list" class="problem-list">${problemCards()}</div>`;
}
function problemTab(name) {
  const p=state.problem;
  if(name==='hints') return `<div class="problem-statement"><h2>先想一步，再看一步。</h2><p>提示按顺序展开，先尝试建立自己的推导。</p></div>`+p.hints.map((h,i)=>`<details class="hint-card"><summary>提示 0${i+1}</summary><p>${escape(h)}</p></details>`).join('');
  if(name==='editorial')return `<div class="reading-content">${markdown(p.editorial)}</div><a class="text-link stack-gap" href="#lesson/${p.lesson_id}">回到关联课程 →</a>`;
  return `<div class="problem-statement"><span class="badge blue">${p.difficulty}</span><h2>${escape(p.title)}</h2><p>${escape(p.statement)}</p><div class="tags">${p.tags.map(t=>`<span class="tag">${escape(t)}</span>`).join('')}</div><h3>输入格式</h3><p>${escape(p.input_format)}</p><h3>输出格式</h3><p>${escape(p.output_format)}</p><h3>数据范围</h3><p>${escape(p.constraints)}</p><h3>样例</h3>${p.samples.map((s,i)=>`<div class="sample"><div><small>输入 ${i+1}</small><pre>${escape(s.input)}</pre></div><div><small>输出 ${i+1}</small><pre>${escape(s.expected_output)}</pre></div></div>`).join('')}</div>`;
}
function executionNotice() {
  return state.health?.execution_backend==='disabled'?`<div class="notice">${icon('alert')}<div>代码执行尚未开启。自己练习时用 <code>uv run --frozen verdictpilot serve --trusted-local</code> 启动，即可编译运行自己的 C++ 代码。课程、检索、笔记功能已可使用。</div></div>`:'';
}
async function labView(id='sum') {
  const p=await api('/v1/problems/'+encodeURIComponent(id)); state.problem=p; state.currentRun=null;
  const code=localStorage.getItem('verdictpilot.draft.'+state.learner+'.'+id) ?? p.draft?.code ?? p.starter_code;
  return heading('训练工作台',p.title,'CODE · TEST · REFLECT',`<a class="button" href="#problems">← 题目列表</a>`)+executionNotice()+`<div class="lab-layout"><section class="lab-problem"><div class="tab-bar"><button class="tab-button active" data-action="problem-tab" data-tab="statement">题目说明</button><button class="tab-button" data-action="problem-tab" data-tab="hints">分层提示</button><button class="tab-button" data-action="problem-tab" data-tab="editorial">思路复盘</button></div><div class="tab-panel" id="problem-panel">${problemTab('statement')}</div></section><section class="lab-editor"><div class="editor-toolbar"><strong>${icon('code')} solution.cpp <span class="badge">C++20</span></strong><span id="draft-status">${p.draft?'草稿已恢复':'自动保存草稿'}</span></div><div class="code-wrap"><div class="line-numbers" id="line-numbers"></div><textarea class="code-editor" id="code-editor" spellcheck="false" aria-label="C++ 代码编辑器">${escape(code)}</textarea></div><div class="editor-footer"><small>Tab 缩进 · Ctrl Enter 提交</small><div><button class="button small" data-action="save-draft">保存</button> <button class="button primary" data-action="submit-code" id="submit-code">运行测试 ${icon('arrow')}</button></div></div><div id="editor-results" class="editor-results">${empty('用一次运行，验证你的想法','测试结果将列出实际输出与预期输出。当前题库结果仅代表这些固定用例。','',true)}</div></section></div>`;
}
function executionResult(run) {
  const report=run.result?.execution;
  if(!report)return `<div class="error-text">${escape(run.error||'这次运行没有执行结果')}</div>`;
  const passed=report.cases.filter(c=>c.status==='passed').length;
  return `<div class="result-title"><strong>${verdictNames[report.status]||report.status}</strong>${badge(report.status)}</div><p class="run-caption">${report.backend} · ${(run.elapsed_ms/1000).toFixed(2)} s ${run.result.case_count?`· ${passed} / ${run.result.case_count} 用例通过`:''}</p>${report.compile_output?`<div class="${report.status==='compile_error'?'error-text':'case-detail'}">${escape(report.compile_output)}</div>`:''}${report.cases.map(c=>`<div class="case-row"><span>${escape(c.name)}</span><span>${badge(c.status)} · ${c.elapsed_ms} ms</span></div>${c.status!=='passed'?`<div class="case-detail">${c.expected_output!==null?'期望：'+escape(c.expected_output):''}\n实际：${escape(c.stdout||'（无输出）')}${c.stderr?'\n错误：'+escape(c.stderr):''}</div>`:''}`).join('')}<div class="result-actions"><a class="button small" href="#run/${run.id}">查看运行证据 ↗</a>${['wrong_answer','compile_error','runtime_error','time_limit','output_limit'].includes(report.status)?`<button class="button small" data-action="add-mistake" data-run="${run.id}">写入错题本</button>`:''}</div>${report.status==='passed'?'<p class="run-caption">通过了本题库测试。可继续补充边界、对拍和复杂度验证。</p>':''}`;
}
async function diagnoseView() {
  const payload=state.diagnosePayload||{title:'网格最短路',statement:'给定 n×m 网格，0 可通行、1 为障碍，求左上角到右下角的最少步数。每次只能上下左右移动。',code:'',test_cases:[]};
  return heading('让诊断，有依据。','带上题面和代码，结合本地知识、执行结果和历史错题进行分析。','DIAGNOSIS WORKBENCH')+executionNotice()+`<div class="diagnosis-grid"><section class="card"><h2>描述这次问题</h2><form id="diagnose-form"><label class="form-field"><span>题目标题</span><input name="title" value="${escape(payload.title)}" required maxlength="200"></label><label class="form-field"><span>题目说明</span><textarea name="statement" required maxlength="30000">${escape(payload.statement)}</textarea></label><label class="form-field"><span>C++ 代码（可选）</span><textarea name="code" spellcheck="false" style="font-family:Consolas,monospace" maxlength="60000">${escape(payload.code||'')}</textarea></label><label class="form-field"><span>测试用例 JSON（可选）</span><textarea name="tests" spellcheck="false" placeholder='[{"name":"sample","input":"2 3\\n","expected_output":"5\\n"}]'>${payload.test_cases?.length?escape(JSON.stringify(payload.test_cases,null,2)):''}</textarea></label><div class="filter-bar"><label class="form-field"><span>分析方式</span><select name="mode"><option value="hint">分层提示</option><option value="diagnose" selected>代码诊断</option><option value="review">方案复核</option></select></label><label class="form-field"><span>推理来源</span><select name="provider"><option value="offline">离线规则 · 无需 Key</option><option value="openai">模型 Agent · 需要 Key</option></select></label></div><button class="button primary" type="submit">开始诊断 ${icon('arrow')}</button></form></section><section class="card diagnosis-result" id="diagnosis-result"><h2>诊断与证据</h2>${empty('先把问题说清楚','离线规则模式按固定流程整合检索与执行结果；配置 Key 后可使用模型驱动的工具调用。')}</section></div>`;
}
async function knowledgeView(docId) {
  const docs=await api('/v1/knowledge/documents');
  const document=docId?await api('/v1/knowledge/documents/'+encodeURIComponent(docId)):null;
  return heading('把知识放在能找到的地方。','搜索算法与工程资料，阅读完整来源，检查片段适用条件。','KNOWLEDGE LIBRARY')+`<form id="knowledge-search-form" class="filter-bar"><input class="filter-input" name="query" placeholder="例如：BFS 入队标记、01 背包倒序" required maxlength="300"><button class="button primary">搜索资料</button></form><div class="knowledge-layout"><section><div class="section-heading"><h2>资料目录</h2><span class="badge">${docs.items.length} 篇</span></div>${docs.items.map(d=>`<a class="document-link" href="#knowledge/${d.id}"><strong>${escape(d.title)} ↗</strong><small>${escape(d.source)}</small></a>`).join('')}</section><section class="article" id="knowledge-content">${document?`<div class="article-header"><span class="badge">${escape(document.source)}</span><h1>${escape(document.title)}</h1></div><div class="reading-content">${markdown(document.body)}</div>`:empty('从一个具体问题开始搜索','来源目录中的文档也可以直接打开。检索排名是相关性信号，使用前仍需核对条件。')}</section></div>`;
}
async function reviewsView() {
  const {items}=await api('/v1/reviews');
  return heading('把错误，变成下一次的优势。','保存有执行证据的错误，用自己的话写教训，再按间隔安排复习。','MISTAKES & REVIEW',`<span class="badge">${items.filter(i=>new Date(i.due_at)<=new Date()).length} 道待复习</span>`)+(items.length?`<div class="review-grid">${items.map(m=>`<article class="review-card"><div class="track-top">${badge(m.symptom)}<span class="badge ${new Date(m.due_at)<=new Date()?'orange':''}">${new Date(m.due_at)<=new Date()?'现在复习':'下次 '+dayDate(m.due_at)}</span></div><h3>${escape(m.problem_title)}</h3><p>${escape(m.lesson)}</p><div class="review-meta">${escape({boundary:'边界条件',complexity:'复杂度',implementation:'实现细节',modeling:'问题建模',other:'其他'}[m.category]||m.category)} · 已复习 ${m.repetitions} 次 · 当前间隔 ${m.interval_days} 天</div><div class="result-actions"><a class="text-link" href="#run/${m.run_id}">原始错误证据 ↗</a>${m.problem_id?`<a class="text-link" href="#lab/${m.problem_id}">重新练习 →</a>`:''}</div><div class="review-controls">${[['again','还没记住'],['hard','想起来很难'],['good','可以复述'],['easy','已熟练']].map(([rating,label])=>`<button class="button small" data-action="review" data-id="${m.id}" data-rating="${rating}">${label}</button>`).join('')}</div></article>`).join('')}</div>`:empty('还没有错题记录','在训练结果里点击“写入错题本”，记下根因和修复方法。没有执行错误证据的记录不能被当作错题。','<a class="button primary" href="#lab/sum">从 A+B 诊断开始</a>'));
}
async function runsView() {
  const data=await api(`/v1/runs?offset=${state.runOffset}&limit=20`);
  return heading('每次运行，都能回到现场。','查看提交结果、诊断回答、代码与工具事件，复盘完整过程。','RUN HISTORY')+runTable(data.items)+`<div class="pager"><span>共 ${data.total} 条 · ${Math.min(state.runOffset+1,data.total)}–${Math.min(state.runOffset+20,data.total)}</span><div><button class="button small" data-action="run-page" data-offset="${Math.max(0,state.runOffset-20)}" ${state.runOffset===0?'disabled':''}>上一页</button> <button class="button small" data-action="run-page" data-offset="${state.runOffset+20}" ${state.runOffset+20>=data.total?'disabled':''}>下一页</button></div></div>`;
}
async function runView(id) {
  const run=await api('/v1/runs/'+encodeURIComponent(id)); state.currentRun=run;
  const result=run.result||{};
  return heading(run.title,`${run.kind==='submission'?'题目训练':'代码诊断'} · ${shortDate(run.created_at)} · ${(run.elapsed_ms/1000).toFixed(2)} s`,'RUN / '+run.id.slice(0,12),'<a href="#runs" class="button">← 运行列表</a>')+`<div class="run-detail-grid"><section class="card">${result.execution?executionResult(run):badge(run.status)}${run.error?`<div class="error-text">${escape(run.error)}</div>`:''}${result.answer_markdown?`<div class="reading-content stack-gap">${markdown(result.answer_markdown)}</div>`:''}${run.code?`<div class="reading-content"><h2>本次代码</h2><pre><code>${escape(run.code)}</code></pre></div>`:''}${run.problem_id?`<a href="#lab/${run.problem_id}" class="button stack-gap">回到题目继续练习 →</a>`:''}</section><aside><section class="card"><h2>运行信息</h2><div class="setting-value"><span>任务状态</span>${badge(run.status)}</div><div class="setting-value"><span>推理来源</span><code>${escape(result.provider||'固定测试集')}</code></div><div class="setting-value"><span>证据编号</span><code>${escape(result.run_id||run.id)}</code></div><h3 class="stack-gap">工具轨迹</h3>${run.events.length?`<div class="timeline">${run.events.map(e=>`<div class="timeline-item"><b>${escape({'workflow.started':'工作流开始','tool.knowledge_search.completed':'知识检索完成','tool.memory_recall.completed':'错题记忆读取','tool.cpp_runner.completed':'代码执行完成','workflow.completed':'回答生成完成'}[e.event]||e.event)}</b><small>${shortDate(e.timestamp)}</small><pre>${escape(JSON.stringify(e.payload,null,2))}</pre></div>`).join('')}</div>`:'<p class="muted stack-gap">这条记录没有模型工具轨迹。代码训练直接使用题库测试，执行证据显示在结果中。</p>'}</section></aside></div>`;
}
async function insightsView() {
  const data=await api('/v1/dashboard');const verdictTotal=data.verdicts.reduce((a,b)=>a+b.count,0);
  return heading('看见节奏，也看见薄弱处。','所有统计来自测验与运行记录；实践任务勾选属于自查，不代表工程能力认证。','LEARNING INSIGHTS')+metricCards(data)+`<div class="insights-grid"><section class="card"><h2>最近 14 天的学习活动</h2>${activityChart(data.activity)}<p class="muted stack-gap">共 ${data.metrics.activity_total} 次测验与运行。日期按北京时间统计。</p></section><section class="card"><h2>代码执行结果分布</h2>${data.verdicts.length?data.verdicts.map(v=>`<div class="distribution-row"><span>${escape(verdictNames[v.verdict]||v.verdict)}</span><div class="progress"><span style="width:${v.count/verdictTotal*100}%"></span></div><strong>${v.count}</strong></div>`).join(''):empty('尚无执行数据','完成一次代码训练后，结果分类会显示在这里。','',true)}</section></div><section class="card stack-gap"><h2>按路线查看测验进度</h2>${data.tracks.map(t=>`<div class="distribution-row" style="grid-template-columns:180px 1fr 48px"><span>${escape(t.title)}</span><div class="progress"><span style="width:${t.passed/t.total*100}%"></span></div><strong>${t.passed}/${t.total}</strong></div>`).join('')}</section>`;
}
async function settingsView() {
  const profile=await api('/v1/profile'); updateProfile(profile);
  return heading('让空间，适合自己的节奏。','管理学习目标和本地档案，导出自己的学习记录与代码证据。','WORKSPACE SETTINGS')+`<div class="settings-grid"><section class="card"><h2>你的学习档案</h2><form id="profile-form" class="stack-gap"><label class="form-field"><span>称呼</span><input name="display_name" value="${escape(profile.display_name)}" required maxlength="40"></label><label class="form-field"><span>当前目标</span><textarea name="goal" maxlength="200">${escape(profile.goal)}</textarea></label><label class="form-field"><span>每日计划时间（分钟）</span><input name="daily_minutes" type="number" min="15" max="240" value="${profile.daily_minutes}" required></label><button class="button primary">保存档案 ${icon('check')}</button></form></section><section class="card"><h2>运行环境与数据</h2><div class="setting-value"><span>平台版本</span><code>${escape(state.health?.version||'0.2.0')}</code></div><div class="setting-value"><span>默认推理来源</span><code>${escape(state.health?.provider||'offline')}</code></div><div class="setting-value"><span>代码执行后端</span><code>${escape(state.health?.execution_backend||'disabled')}</code></div><div class="setting-value"><span>当前本地档案</span><code>${escape(state.learner.slice(0,20))}…</code></div><p class="muted stack-gap">当前版本用于本机个人学习。档案 ID 保存在此浏览器；它不是账户鉴权。数据库保存测验、草稿、提交和错题。</p><button class="button stack-gap" data-action="export">导出我的学习证据 ↗</button><p class="muted stack-gap">启动自己的可信代码练习：<br><code>uv run --frozen verdictpilot serve --trusted-local</code></p><a class="text-link stack-gap" href="/docs" target="_blank" rel="noopener">查看接口文档 ↗</a></section></div>`;
}
function updateProfile(profile) {
  const initial=Array.from(profile.display_name)[0]||'学';$('#side-avatar').textContent=initial;$('#top-avatar').textContent=initial;
  $('#side-name').innerHTML=escape(profile.display_name)+'<small>本地学习档案</small>';
}
async function render() {
  const token=++state.routeToken; const [route,arg]=(location.hash.slice(1)||'dashboard').split('/');
  const active={lesson:'courses',lab:'problems',run:'runs'}[route]||route;
  $('#navigation').innerHTML=nav.map(n=>`${n[0]==='reviews'?'<div class="nav-section">REVIEW & GROW</div>':''}<a href="#${n[0]}" class="nav-link ${n[0]===active?'active':''}" ${n[0]===active?'aria-current="page"':''} title="${n[1]}">${icon(n[2])}<span>${n[1]}</span></a>`).join('');
  $('#page-label').textContent=nav.find(n=>n[0]===active)?.[1]||'学习空间';$('#sidebar').classList.remove('open');
  main.innerHTML='<div class="loading-state"><div class="spinner"></div>正在读取你的学习记录…</div>';
  try {
    const views={dashboard:dashboardView,courses:coursesView,lesson:lessonView,problems:problemsView,lab:labView,diagnose:diagnoseView,knowledge:knowledgeView,projects:projectsView,reviews:reviewsView,runs:runsView,run:runView,insights:insightsView,settings:settingsView};
    const html=await (views[route]||dashboardView)(arg);
    if(token!==state.routeToken)return;
    main.innerHTML=html;window.scrollTo({top:0,behavior:'instant'});
    if(route==='lab')updateLines();
    if(route==='run'&&['queued','running'].includes(state.currentRun?.status)) pollRun(state.currentRun.id,token,'detail');
    document.title=`${$('#page-label').textContent} · VerdictPilot`;
  } catch(error) {
    if(token!==state.routeToken)return;
    main.innerHTML=empty('暂时无法打开这一页',error.message,'<button class="button" data-action="retry">重新加载</button>');
  }
}
function updateLines() {
  const editor=$('#code-editor');if(!editor)return;
  $('#line-numbers').textContent=Array.from({length:editor.value.split('\n').length},(_,i)=>i+1).join('\n');
}
async function saveDraft(showToast=false) {
  const editor=$('#code-editor');if(!editor||!state.problem)return;
  return persistDraft(state.problem.id,editor.value,showToast);
}
async function persistDraft(id,code,showToast=false) {
  localStorage.setItem('verdictpilot.draft.'+state.learner+'.'+id,code);
  try {await put('/v1/problems/'+id+'/draft',{code});if($('#draft-status')&&state.problem?.id===id)$('#draft-status').textContent='草稿已保存';if(showToast)toast('草稿已保存');}
  catch(error){if($('#draft-status'))$('#draft-status').textContent='服务保存失败，已留在浏览器';if(showToast)toast(error.message,true);}
}
async function saveNote(showToast=false) {
  const node=$('#lesson-note');if(!node||!state.lesson)return;
  return persistNote(state.lesson.id,node.value,$('#exercise-done').checked,showToast);
}
async function persistNote(id,note,exerciseDone,showToast=false) {
  try {await put('/v1/lessons/'+id+'/note',{note,exercise_done:exerciseDone});if($('#note-status')&&state.lesson.id===id)$('#note-status').textContent='已保存 · '+shortDate(new Date());if(showToast)toast('笔记已保存');}
  catch(error){if($('#note-status'))$('#note-status').textContent='保存失败，请重试';toast(error.message,true);}
}
async function pollRun(id,token,target='editor') {
  let attempts=0;
  while(token===state.routeToken&&attempts++<240) {
    const run=await api('/v1/runs/'+id);
    if(token!==state.routeToken)return;
    if(!['queued','running'].includes(run.status)) {
      state.currentRun=run;
      if(target==='detail'){render();return;}
      $('#editor-results').innerHTML=executionResult(run);
      const button=$('#submit-code');if(button)button.disabled=false;
      return;
    }
    if(target==='editor')$('#editor-results').innerHTML=`<div class="loading-state" style="padding:25px"><div class="spinner"></div>${run.status==='queued'?'已进入提交队列':'正在编译并运行题库测试'}…<span class="muted">任务已保存，离开页面后可在运行记录查看</span></div>`;
    await new Promise(resolve=>setTimeout(resolve,750));
  }
  if(token===state.routeToken&&target==='editor') {
    $('#editor-results').innerHTML=`<p class="muted">任务仍在运行，可到运行记录查看。</p><a class="text-link" href="#run/${id}">打开任务 →</a>`;
    $('#submit-code').disabled=false;
  }
}
async function submitCode() {
  const button=$('#submit-code'); if(!button||button.disabled)return;button.disabled=true;
  const token=state.routeToken;
  try {const data=await post('/v1/problems/'+state.problem.id+'/submit',{code:$('#code-editor').value});await pollRun(data.run_id,token);}
  catch(error){if(token===state.routeToken){$('#editor-results').innerHTML=`<div class="error-text">${escape(error.message)}</div>`;button.disabled=false;}}
}
function mistakeDialog(runId) {
  $('#mistake-dialog')?.remove();
  const dialog=document.createElement('dialog');dialog.id='mistake-dialog';dialog.className='search-dialog';
  dialog.innerHTML=`<div class="card" style="border:0"><h2>把这次错误变成教训</h2><p class="muted" style="margin:8px 0 20px">写下你确认的原因和修复方法，而不只复制诊断建议。</p><form id="mistake-form" data-run="${escape(runId)}"><label class="form-field"><span>错误类别</span><select name="category"><option value="boundary">边界条件</option><option value="implementation">实现细节</option><option value="modeling">问题建模</option><option value="complexity">复杂度</option><option value="other">其他</option></select></label><label class="form-field"><span>我学到的教训</span><textarea name="lesson" required minlength="3" maxlength="3000" placeholder="例如：先查询补数，再插入当前元素，避免元素和自己配对。"></textarea></label><div class="result-actions"><button type="submit" class="button primary">保存并安排复习</button><button type="button" class="button" data-action="close-mistake">取消</button></div></form></div>`;
  document.body.append(dialog);dialog.showModal();
}
async function openSearch() {
  if(!state.catalog)state.catalog=await api('/v1/catalog');
  if(!state.problemIndex)state.problemIndex=await api('/v1/problems');
  $('#search-dialog').showModal();$('#global-search').value='';searchResults('');$('#global-search').focus();
}
function searchResults(query) {
  const items=[...state.catalog.lessons.map(l=>({title:l.title,type:'课程',href:'#lesson/'+l.id,keywords:l.description})),...state.problemIndex.items.map(p=>({title:p.title,type:'训练题',href:'#lab/'+p.id,keywords:p.tags.join(' ')}))];
  const matches=items.filter(i=>(i.title+i.keywords).toLowerCase().includes(query.toLowerCase())).slice(0,10);
  $('#search-results').innerHTML=matches.length?matches.map(i=>`<a class="search-result" href="${i.href}" data-action="search-result">${icon(i.type==='课程'?'book':'code')}${escape(i.title)}<small>${i.type} ↗</small></a>`).join(''):empty('没有找到结果','换一个算法名或课程关键词试试。','',true);
}
document.addEventListener('click',async event=>{
  const node=event.target.closest('[data-action]');if(!node)return;
  try {
    switch(node.dataset.action) {
      case 'retry':render();break;
      case 'search':await openSearch();break;
      case 'close-search':case 'search-result':$('#search-dialog').close();break;
      case 'problem-tab':$('.tab-button.active').classList.remove('active');node.classList.add('active');$('#problem-panel').innerHTML=problemTab(node.dataset.tab);break;
      case 'filter-tag':state.tag=node.dataset.tag;document.querySelectorAll('[data-action="filter-tag"]').forEach(n=>n.classList.toggle('active',n===node));$('#problem-list').innerHTML=problemCards();break;
      case 'save-draft':await saveDraft(true);break;
      case 'save-note':await saveNote(true);break;
      case 'submit-code':await submitCode();break;
      case 'add-mistake':mistakeDialog(node.dataset.run);break;
      case 'close-mistake':$('#mistake-dialog').close();break;
      case 'review':await post(`/v1/reviews/${node.dataset.id}/practice`,{rating:node.dataset.rating});toast('复习反馈已保存，下一次时间已更新');render();break;
      case 'run-page':state.runOffset=Number(node.dataset.offset);render();break;
      case 'export':{
        const data=await api('/v1/export');const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='verdictpilot-learning-evidence.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);toast('学习证据已导出');break;
      }
    }
  } catch(error){toast(error.message,true);}
});
document.addEventListener('submit',async event=>{
  const form=event.target;if(!['quiz-form','diagnose-form','profile-form','knowledge-search-form','mistake-form','project-evidence-form'].includes(form.id))return;
  event.preventDefault();const button=$('button[type="submit"],button:not([type])',form);if(button)button.disabled=true;
  const data=new FormData(form);const token=state.routeToken;
  try {
    if(form.id==='quiz-form') {
      const result=await post('/v1/lessons/'+state.lesson.id+'/quiz',{answers:state.lesson.quiz.map((_,i)=>Number(data.get('q'+i)))});
      if(token!==state.routeToken)return;
      $('#quiz-feedback').innerHTML=`<div class="quiz-feedback ${result.passed?'':'error'}"><strong>${result.score} 分 · ${result.passed?'测验通过':'再回到概念看一看'}</strong>${result.questions.map((q,i)=>`<p style="margin-top:9px">${q.correct?'✓':'↺'} 第 ${i+1} 题：${escape(q.explanation)}</p>`).join('')}</div>`;
      $('#best-score').textContent=Math.max(result.score,state.lesson.progress?.best_score||0)+' 分';state.catalog=null;toast(result.passed?'测验通过，进度已保存':'已记录成绩，可阅读解析后再次尝试');
    } else if(form.id==='diagnose-form') {
      const tests=String(data.get('tests')).trim();let cases=[];
      if(tests){try{cases=JSON.parse(tests);}catch{throw new Error('测试用例 JSON 格式不正确');}if(!Array.isArray(cases))throw new Error('测试用例应该是 JSON 数组');}
      const payload={title:data.get('title'),statement:data.get('statement'),code:data.get('code')||null,test_cases:cases,mode:data.get('mode'),provider:data.get('provider'),session_id:state.learner};state.diagnosePayload=payload;
      $('#diagnosis-result').innerHTML='<div class="loading-state"><div class="spinner"></div>正在检索资料并整合证据…</div>';
      const result=await post('/v1/analyze',payload);if(token!==state.routeToken)return;
      $('#diagnosis-result').innerHTML=`<div class="section-heading"><h2>诊断与证据</h2><span class="badge">${result.provider==='offline'?'离线规则':'模型 Agent'}</span></div><div class="reading-content">${markdown(result.answer_markdown)}</div><div class="result-actions"><a class="button small" href="#run/${result.platform_run_id}">查看调用轨迹 ↗</a>${['wrong_answer','compile_error','runtime_error','time_limit','output_limit'].includes(result.execution?.status)?`<button class="button small" data-action="add-mistake" data-run="${result.platform_run_id}">写入错题本</button>`:''}</div><section class="sources"><h3>检索来源</h3>${result.retrieved.map(d=>`<a class="source-card" style="display:block" href="#knowledge/${d.doc_id}"><h3>${escape(d.title)} ↗</h3><p>${escape(d.snippet)}</p><small>${escape(d.source)} · score ${d.score}</small></a>`).join('')}</section>`;
    } else if(form.id==='profile-form') {
      const profile=await put('/v1/profile',{display_name:data.get('display_name'),goal:data.get('goal'),daily_minutes:Number(data.get('daily_minutes'))});updateProfile(profile);toast('学习档案已保存');
    } else if(form.id==='knowledge-search-form') {
      const items=await api('/v1/knowledge/search?q='+encodeURIComponent(data.get('query')));
      $('#knowledge-content').innerHTML=`<h2>搜索结果</h2><p class="muted stack-gap">${items.length} 篇相关资料 · 点击打开完整来源</p>${items.map(d=>`<a href="#knowledge/${d.doc_id}" class="source-card" style="display:block"><h3>${escape(d.title)} ↗</h3><p>${escape(d.snippet)}</p><small>${escape(d.source)} · score ${d.score}</small></a>`).join('')||empty('没有命中资料','可在 knowledge 目录补充对应算法笔记，再重新索引。')}`;
    } else if(form.id==='project-evidence-form') {
      const milestone=state.currentProject.milestones.find(m=>m.id===form.dataset.milestone);
      const metrics=Object.fromEntries(milestone.metrics.map(m=>[m,Number(data.get('metric_'+m))]));
      await put(`/v1/projects/${form.dataset.project}/milestones/${form.dataset.milestone}`,{summary:data.get('summary'),command:data.get('command'),artifact:data.get('artifact'),metrics});
      toast('里程碑证据已保存');render();
    } else if(form.id==='mistake-form') {
      await post('/v1/reviews',{run_id:form.dataset.run,category:data.get('category'),lesson:data.get('lesson')});$('#mistake-dialog').close();toast('教训已保存，可以到错题本进行复习');
    }
  } catch(error){toast(error.message,true);if(form.id==='diagnose-form'&&token===state.routeToken)$('#diagnosis-result').innerHTML=`<h2>诊断暂未完成</h2><div class="error-text">${escape(error.message)}</div>`;}
  finally {if(button)button.disabled=false;}
});
document.addEventListener('input',event=>{
  const node=event.target;
  if(node.id==='problem-search'){state.problemSearch=node.value;$('#problem-list').innerHTML=problemCards();}
  if(node.id==='global-search')searchResults(node.value);
  if(node.id==='code-editor'){updateLines();const id=state.problem.id,code=node.value;localStorage.setItem('verdictpilot.draft.'+state.learner+'.'+id,code);$('#draft-status').textContent='正在保存…';clearTimeout(draftTimer);draftTimer=setTimeout(()=>persistDraft(id,code),700);}
  if(node.id==='lesson-note'){const id=state.lesson.id,note=node.value,done=$('#exercise-done').checked;clearTimeout(noteTimer);$('#note-status').textContent='正在保存…';noteTimer=setTimeout(()=>persistNote(id,note,done),700);}
});
document.addEventListener('change',event=>{
  if(event.target.id==='difficulty-filter'){state.difficulty=event.target.value;$('#problem-list').innerHTML=problemCards();}
  if(event.target.id==='exercise-done')saveNote();
  if(event.target.id==='milestone-select'){state.selectedMilestone=event.target.value;$('#project-evidence-panel').innerHTML=evidenceForm(state.currentProject,state.currentProject.milestones.find(m=>m.id===state.selectedMilestone));}
});
document.addEventListener('keydown',event=>{
  if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='k'){event.preventDefault();openSearch().catch(e=>toast(e.message,true));}
  if(event.target.id==='code-editor') {
    if(event.key==='Tab'){event.preventDefault();const e=event.target;e.setRangeText('    ',e.selectionStart,e.selectionEnd,'end');e.dispatchEvent(new Event('input',{bubbles:true}));}
    if((event.ctrlKey||event.metaKey)&&event.key==='Enter'){event.preventDefault();submitCode();}
  }
});
document.addEventListener('scroll',event=>{if(event.target.id==='code-editor')$('#line-numbers').scrollTop=event.target.scrollTop;},true);
$('#menu-toggle').addEventListener('click',()=>$('#sidebar').classList.toggle('open'));
window.addEventListener('hashchange',()=>{$('#search-dialog').close();render();});
async function initialize() {
  try {state.health=await api('/health');$('#connection').textContent=state.health.execution_backend==='disabled'?'离线学习就绪':'代码训练就绪';}
  catch {$('#connection').textContent='服务未连接';$('#connection').classList.add('offline');}
  await render();
}
initialize();
