/* SwitchBot IR panel — vanilla web component for Home Assistant (admin only). */

const API = "switchbot_ir";
const SLUG_RE = /^[a-z0-9_]{1,40}$/;

const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

// 標準コマンド一覧(出典: SwitchBot API 公式ドキュメント「Virtual infrared remote devices」)
const REF_URL = "https://github.com/OpenWonderLabs/SwitchBotAPI/blob/main/devices/others/virtual-infrared-remote-devices.md";
const CMD_GROUPS = [
  { id: "common", title: "共通(「その他」を除く、すべての家電)", types: ["*"], rows: [
    ["turnOn", "default", "電源を入れる"],
    ["turnOff", "default", "電源を切る"],
  ] },
  { id: "ac", title: "エアコン", types: ["Air Conditioner"], rows: [
    ["setAll", "{温度},{モード},{風量},{電源}", "温度・モード・風量・電源をまとめて設定します。例 26,1,3,on", "26,1,3,on"],
  ], note: "温度は摂氏です。モード: 0/1=自動、2=冷房、3=除湿、4=送風、5=暖房。風量: 1=自動、2=弱、3=中、4=強。電源: on / off。" },
  { id: "tv", title: "テレビ・IPTV/ストリーマー・セットトップボックス", types: ["TV", "IPTV", "Streamer", "Set Top Box"], rows: [
    ["SetChannel", "チャンネル番号(例 15)", "チャンネルを指定して切り替える", "15"],
    ["volumeAdd", "default", "音量を上げる"],
    ["volumeSub", "default", "音量を下げる"],
    ["channelAdd", "default", "次のチャンネル"],
    ["channelSub", "default", "前のチャンネル"],
  ] },
  { id: "dvd", title: "DVD・スピーカー", types: ["DVD", "DVD Player", "Speaker"], rows: [
    ["setMute", "default", "ミュート / ミュート解除"],
    ["FastForward", "default", "早送り"],
    ["Rewind", "default", "巻き戻し"],
    ["Next", "default", "次のトラック"],
    ["Previous", "default", "前のトラック"],
    ["Pause", "default", "一時停止"],
    ["Play", "default", "再生 / 再開"],
    ["Stop", "default", "停止"],
  ] },
  { id: "speaker", title: "スピーカー", types: ["Speaker"], rows: [
    ["volumeAdd", "default", "音量を上げる"],
    ["volumeSub", "default", "音量を下げる"],
  ] },
  { id: "fan", title: "扇風機", types: ["Fan"], rows: [
    ["swing", "default", "首振り"],
    ["timer", "default", "タイマーの設定"],
    ["lowSpeed", "default", "風量を弱にする"],
    ["middleSpeed", "default", "風量を中にする"],
    ["highSpeed", "default", "風量を強にする"],
  ] },
  { id: "light", title: "ライト", types: ["Light"], rows: [
    ["brightnessUp", "default", "明るくする"],
    ["brightnessDown", "default", "暗くする"],
  ] },
  { id: "others", title: "その他(Others)", types: ["Others"], rows: [],
    note: "標準コマンドはありません。SwitchBotアプリで登録したボタンは、種別を「カスタムボタン」にして、ボタン名を入力してください。" },
];

const CSS_EXTRA = `
a { color:var(--primary-color); }
.dialog.wide { width:min(760px,100%); }
.refgroup { margin:16px 0 0; }
.refhead { display:flex; flex-wrap:wrap; align-items:center; gap:6px 10px; }
.tag { padding:1px 8px; border-radius:10px; font-size:12px; background:var(--primary-color); color:var(--text-primary-color, #fff); }
.scroll { overflow-x:auto; }
.reftable { width:100%; border-collapse:collapse; font-size:13px; }
.reftable td { padding:6px 8px 6px 0; border-top:1px solid var(--divider-color); vertical-align:top; }
.reftable td:last-child { text-align:right; white-space:nowrap; }
.reftable code { font-family:monospace; font-size:13px; }
`;

const TYPE_UI = {
  customize: {
    label: "ボタン名",
    hint: "SwitchBotアプリで、このリモコンに登録したボタンの名前を、そのまま入力してください(大文字小文字・空白も一致させます)。",
    placeholder: "電源",
    param: false,
    testNote: true,
  },
  command: {
    label: "ボタン名",
    hint: '利用できる標準のコマンド名は<a href="#" data-act="cmdRef">こちら</a>を参照してください。',
    placeholder: "turnOn",
    param: true,
    testNote: false,
  },
};

const TEST_NOTE = "テスト送信に失敗するボタンが、SwitchBotアプリで操作ができる場合は、種別を標準コマンドに変更して試してください。";
const MAIN_IDS = { type: "cmdType", label: "cmdLabel", hint: "cmdHint", param: "paramRow", cmd: "cmd", testNote: "testNote" };
const EDIT_IDS = { type: "eType", label: "eCmdLabel", hint: "eCmdHint", param: "eParamRow", cmd: "eCmd", testNote: "eTestNote" };

const CSS = `
:host { display:block; min-height:100vh; background:var(--primary-background-color); color:var(--primary-text-color);
  font-family:var(--paper-font-body1_-_font-family, Roboto, "Noto Sans JP", sans-serif); font-size:14px; }
header { display:flex; align-items:center; gap:8px; height:56px; padding:0 12px;
  background:var(--app-header-background-color, var(--primary-color)); color:var(--app-header-text-color, #fff); }
h1 { margin:0; font-size:20px; font-weight:400; }
main { max-width:860px; margin:0 auto; padding:4px 16px 64px; }
section { padding:22px 0; border-bottom:1px solid var(--divider-color); }
section:last-child { border-bottom:0; }
h2 { margin:0 0 12px; font-size:16px; font-weight:500; }
h3 { margin:0 0 12px; font-size:18px; font-weight:500; }
p { margin:0 0 10px; line-height:1.6; }
label { display:block; margin:14px 0 4px; font-size:13px; color:var(--secondary-text-color); }
.hint, .state, .sub { color:var(--secondary-text-color); font-size:13px; }
.warn { color:var(--warning-color, #b26a00); }
.err { color:var(--error-color); min-height:18px; font-size:13px; }
.empty { color:var(--secondary-text-color); }
button { font:inherit; min-height:36px; padding:6px 14px; border-radius:8px; cursor:pointer;
  border:1px solid var(--divider-color); background:var(--card-background-color); color:var(--primary-text-color); }
button.primary { background:var(--primary-color); color:var(--text-primary-color, #fff); border-color:transparent; }
button.danger { color:var(--error-color); }
button:disabled { opacity:.5; cursor:default; }
:host(.working) button { pointer-events:none; opacity:.6; }
:focus-visible { outline:2px solid var(--primary-color); outline-offset:2px; }
input, select { font:inherit; box-sizing:border-box; width:100%; min-height:36px; padding:6px 10px; border-radius:8px;
  border:1px solid var(--divider-color); background:var(--card-background-color); color:var(--primary-text-color); }
input.invalid { border-color:var(--error-color); }
.row { display:flex; flex-wrap:wrap; align-items:center; gap:8px; }
.row select { flex:1 1 220px; width:auto; }
.idrow { display:flex; }
.prefix { display:flex; align-items:center; padding:0 10px; white-space:nowrap; font-family:monospace; color:var(--secondary-text-color);
  background:var(--secondary-background-color); border:1px solid var(--divider-color); border-right:0; border-radius:8px 0 0 8px; }
.idrow input { border-radius:0 8px 8px 0; font-family:monospace; }
.banner { padding:10px 12px; border-radius:8px; margin:10px 0; background:var(--secondary-background-color); line-height:1.6; }
.banner.warn { border-left:4px solid var(--warning-color, #b26a00); }
.list { list-style:none; margin:0; padding:0; }
.list li { display:flex; align-items:center; gap:12px; padding:10px 0; border-top:1px solid var(--divider-color); }
.list li:first-child { border-top:0; }
.list ha-icon { flex:none; color:var(--secondary-text-color); }
.list .main { flex:1; min-width:0; }
.list .name { font-weight:500; overflow-wrap:anywhere; }
.meta { display:flex; flex-wrap:wrap; gap:2px 14px; }
.actions { display:flex; flex:none; gap:6px; flex-wrap:wrap; justify-content:flex-end; }
#msg { position:sticky; top:0; z-index:5; }
.toast { padding:10px 16px; white-space:pre-line; line-height:1.5; background:var(--primary-text-color); color:var(--primary-background-color); }
.toast.error { background:var(--error-color); color:#fff; }
.toast.warn { background:var(--warning-color, #b26a00); color:#fff; }
.backdrop { position:fixed; inset:0; z-index:10; display:flex; align-items:center; justify-content:center; padding:16px; background:rgba(0,0,0,.5); }
.dialog { width:min(480px,100%); max-height:90vh; overflow:auto; padding:20px; border-radius:12px;
  background:var(--card-background-color); color:var(--primary-text-color); }
.dialog .actions { margin-top:20px; justify-content:flex-end; }
.refs { margin:8px 0; padding-left:18px; font-size:13px; overflow-wrap:anywhere; }
ol.steps { margin:0 0 8px; padding-left:22px; line-height:1.8; }
.note { margin:0 0 12px; font-size:13px; line-height:1.6; color:var(--secondary-text-color); }
details { margin-top:16px; padding:0 12px; border:1px solid var(--divider-color); border-radius:8px; }
summary { padding:10px 0; font-weight:500; cursor:pointer; }
details[open] > summary { margin-bottom:2px; }
@media (max-width:560px) { .list li { flex-wrap:wrap; } .actions { width:100%; justify-content:flex-start; } }
.pick { margin-top:16px; }
`;

class SwitchBotIrPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.s = { st: null, remotes: [], remErr: "", sel: "", regIcon: "", regArea: "", aliasTouched: false, buttons: [], buttonsErr: "", modal: null, ref: null };
    this._pickers = new Set();
    this._ready = false;
    this._working = false;
  }

  set hass(hass) {
    this._hass = hass;
    this._pickers.forEach((p) => { p.hass = hass; });
    if (this._menu) this._menu.hass = hass;
    if (!this._ready) {
      this._ready = true;
      this._init();
    }
  }

  set narrow(v) {
    this._narrow = v;
    if (this._menu) this._menu.narrow = v;
  }

  // ------------------------------------------------------------------ setup

  _init() {
    const root = this.shadowRoot;
    root.innerHTML = `<style>${CSS}${CSS_EXTRA}</style>
      <header><span id="menuSlot"></span><h1>SwitchBot IR</h1></header>
      <div id="msg" role="status" aria-live="polite"></div>
      <main><section id="secCloud"></section><section id="secRemote"></section><section id="secList"></section></main>
      <div id="modal"></div><div id="refModal"></div>`;
    if (customElements.get("ha-menu-button")) {
      const m = document.createElement("ha-menu-button");
      m.hass = this._hass;
      m.narrow = this._narrow;
      root.getElementById("menuSlot").appendChild(m);
      this._menu = m;
    }
    root.addEventListener("click", (e) => this._onClick(e));
    root.addEventListener("change", (e) => this._onChange(e));
    root.addEventListener("input", (e) => this._onInput(e));
    root.addEventListener("keydown", (e) => {
      if (e.key !== "Escape") return;
      if (this.s.ref) this._closeRef();
      else if (this.s.modal) this._closeModal();
    });
    this._renderCloud();
    this._renderRemote();
    this._renderList();
    this._work(async () => {
      await this._loadStatus();
      await this._loadRemotes();
      await this._loadButtons();
    });
  }

  async _api(method, path, body) {
    try {
      return await this._hass.callApi(method, `${API}/${path}`, body);
    } catch (e) {
      const b = e && e.body && typeof e.body === "object" ? e.body : {};
      const err = new Error(b.error || b.message || (e && (e.error || e.message)) || "通信に失敗しました");
      err.body = b;
      err.status = e && e.status_code;
      throw err;
    }
  }

  async _work(fn) {
    if (this._working) return;
    this._working = true;
    this.classList.add("working");
    try {
      await fn();
    } catch (e) {
      this._toast(e.message || String(e), "error");
    } finally {
      this._working = false;
      this.classList.remove("working");
    }
  }

  _toast(text, kind = "info") {
    const el = this.shadowRoot.getElementById("msg");
    el.innerHTML = `<div class="toast ${kind}">${esc(text)}</div>`;
    clearTimeout(this._tt);
    this._tt = setTimeout(() => { el.innerHTML = ""; }, kind === "info" ? 6000 : 14000);
  }

  _q(id) {
    const el = this.shadowRoot.getElementById(id);
    return el ? el.value.trim() : "";
  }

  // ---------------------------------------------------------------- loading

  async _loadStatus() {
    this.s.st = await this._api("GET", "status");
    this._renderCloud();
  }

  async _loadRemotes() {
    try {
      const r = await this._api("GET", "remotes");
      this.s.remotes = r.remotes;
      this.s.remErr = "";
    } catch (e) {
      this.s.remotes = [];
      this.s.remErr = e.message;
    }
    if (!this.s.remotes.some((x) => x.device_id === this.s.sel)) this.s.sel = this.s.remotes[0]?.device_id || "";
    this._renderRemote();
  }

  async _loadButtons() {
    try {
      const r = await this._api("GET", "buttons");
      this.s.buttons = r.buttons;
      this.s.buttonsErr = "";
    } catch (e) {
      this.s.buttons = [];
      this.s.buttonsErr = e.message;
    }
    this._renderList();
  }

  // -------------------------------------------------------------- rendering

  _sec(id, html) {
    this.shadowRoot.getElementById(id).innerHTML = html;
  }

  _iconField(slot, value, onChange) {
    this._pickers.forEach((p) => { if (!p.isConnected) this._pickers.delete(p); });
    slot.textContent = "";
    let el;
    const label = "アイコン(任意)";
    if (customElements.get("ha-selector")) {
      el = document.createElement("ha-selector");
      el.hass = this._hass;
      el.selector = { icon: {} };
      el.value = value || "";
      el.label = label;
      el.required = false;
      el.addEventListener("value-changed", (e) => { e.stopPropagation(); onChange(e.detail.value || ""); });
    } else if (customElements.get("ha-icon-picker")) {
      el = document.createElement("ha-icon-picker");
      el.hass = this._hass;
      el.value = value || "";
      el.label = label;
      el.addEventListener("value-changed", (e) => { e.stopPropagation(); onChange(e.detail.value || ""); });
    } else {
      // フォールバック: テキスト入力
      slot.innerHTML = `<label for="iconText">${label}</label><input id="iconText" placeholder="mdi:television" autocomplete="off" spellcheck="false">`;
      el = slot.querySelector("input");
      el.value = value || "";
      el.addEventListener("input", () => onChange(el.value.trim()));
      return;
    }
    this._pickers.add(el);
    slot.appendChild(el);
  }

  _areaField(slot, value, onChange) {
    this._pickers.forEach((p) => { if (!p.isConnected) this._pickers.delete(p); });
    slot.textContent = "";
    let el;
    const label = "エリア(任意)";
    if (customElements.get("ha-selector")) {
      el = document.createElement("ha-selector");
      el.hass = this._hass;
      el.selector = { area: {} };
      el.value = value || "";
      el.label = label;
      el.required = false;
      el.addEventListener("value-changed", (e) => { e.stopPropagation(); onChange(e.detail.value || ""); });
    } else if (customElements.get("ha-area-picker")) {
      el = document.createElement("ha-area-picker");
      el.hass = this._hass;
      el.value = value || "";
      el.label = label;
      el.addEventListener("value-changed", (e) => { e.stopPropagation(); onChange(e.detail.value || ""); });
    } else {
      // フォールバック: HAのエリア一覧から選ぶ
      const areas = Object.values((this._hass && this._hass.areas) || {})
        .sort((a, b) => String(a.name).localeCompare(String(b.name), "ja"));
      slot.innerHTML = `<label for="areaSel">${label}</label><select id="areaSel"><option value="">(指定なし)</option>` +
        areas.map((a) => `<option value="${esc(a.area_id)}">${esc(a.name)}</option>`).join("") + `</select>`;
      el = slot.querySelector("select");
      el.value = value || "";
      el.addEventListener("change", () => onChange(el.value));
      return;
    }
    this._pickers.add(el);
    slot.appendChild(el);
  }

  _renderCloud() {
    const st = this.s.st;
    if (!st) {
      this._sec("secCloud", `<h2>SwitchBot クラウド</h2><p class="hint">読み込み中…</p>`);
      return;
    }
    if (!st.configured) {
      this._sec("secCloud", `<h2>SwitchBot クラウド</h2><p class="empty">トークンとシークレットが未設定です。</p>
        <div class="row"><button class="primary" data-act="editCred">トークンとシークレットを設定</button></div>`);
      return;
    }
    const state = st.fetched_at
      ? `赤外線リモコン ${esc(st.count)}台、最終取得 ${esc(new Date(st.fetched_at).toLocaleString("ja-JP"))}`
      : "まだ情報を取得していません。「情報を取得」を押してください。";
    this._sec("secCloud", `<h2>SwitchBot クラウド</h2>
      <div class="row"><button${st.fetched_at ? "" : ' class="primary"'} data-act="fetch" title="クラウドに問い合わせて、赤外線リモコンの一覧を取得します(押したときだけ通信します)">情報を取得</button>
        <button data-act="editCred">設定</button></div>
      <p class="state">${state}<br>本日のAPI呼び出し(このコンポーネントの分): ${esc(st.calls_today)}/${esc(st.daily_limit)}回</p>
      ${st.auth_failed ? `<div class="banner warn">認証に失敗しました。トークン・シークレットが無効(リセットされた可能性)か、1日の上限を超えた可能性があります。「設定」を確認してください。</div>` : ""}`);
  }

  _typeOptions(selected) {
    return `<option value="customize"${selected === "customize" ? " selected" : ""}>カスタムボタン(SwitchBotアプリで学習させたボタン)</option>
      <option value="command"${selected === "command" ? " selected" : ""}>標準コマンド(turnOn・turnOffなど)</option>`;
  }

  // 種別に応じて、ラベル・説明・パラメータ欄・テスト送信の注記の表示を切り替える(入力済みの内容は消さない)
  _applyTypeUi(ids) {
    const sel = this.shadowRoot.getElementById(ids.type);
    if (!sel) return;
    const ui = TYPE_UI[sel.value] || TYPE_UI.customize;
    const set = (id, fn) => { const el = this.shadowRoot.getElementById(id); if (el) fn(el); };
    set(ids.label, (el) => { el.textContent = ui.label; });
    set(ids.hint, (el) => { el.innerHTML = ui.hint; });
    set(ids.param, (el) => { el.style.display = ui.param ? "" : "none"; });
    set(ids.cmd, (el) => { el.placeholder = ui.placeholder; });
    set(ids.testNote, (el) => { el.style.display = ui.testNote ? "" : "none"; });
  }

  _renderRemote() {
    const { st, remotes, remErr, sel } = this.s;
    if (!st || !st.configured) { this._sec("secRemote", ""); return; }
    let html = `<h2>ボタンを登録</h2>`;
    if (remErr) {
      this._sec("secRemote", html + `<div class="banner warn">${esc(remErr)}</div>`);
      return;
    }
    if (!remotes.length) {
      this._sec("secRemote", html + `<p class="empty">赤外線リモコンの一覧がありません。上の「情報を取得」を押してください。SwitchBotアプリで、ハブに赤外線リモコンを追加しておく必要があります。</p>`);
      return;
    }
    const cur = remotes.find((x) => x.device_id === sel) || remotes[0];
    const opts = remotes
      .map((x) => `<option value="${esc(x.device_id)}"${x.device_id === cur.device_id ? " selected" : ""}>${esc(x.label)}</option>`)
      .join("");
    html += `<ol class="steps"><li>登録するリモコンを選んでください。</li>
        <li>種別とボタン名を入力し、必要なら「テスト送信」で動作を確認してください。</li></ol>
      <p class="note">※テスト送信は、クラウド経由で実際に信号を送信します。</p>
      <div class="row"><select id="remSel" aria-label="リモコン">${opts}</select></div>`;
    if (cur.buttons.length) {
      html += `<p class="hint" style="margin-top:10px">このリモコンで登録済み: ${cur.buttons.map((sc) => `${esc(sc.entity_id)}(${esc(sc.command)})`).join("、")}</p>`;
    }
    html += `<label for="cmdType">種別</label>
      <select id="cmdType">${this._typeOptions(cur.default_type)}</select>
      <label for="cmd" id="cmdLabel">ボタン名</label>
      <input id="cmd" maxlength="80" autocomplete="off" spellcheck="false">
      <p class="hint" id="cmdHint"></p>
      <div id="paramRow"><label for="param">パラメータ(任意)</label>
        <input id="param" placeholder="default" maxlength="200" autocomplete="off" spellcheck="false">
        <p class="hint">空欄なら default を送ります。エアコンの setAll は「温度,モード,風量,電源」の形で入力します(例 26,2,3,on)。</p></div>
      <div class="row" style="margin-top:12px"><button data-act="testSend">テスト送信</button></div>
      <p class="note" id="testNote" style="margin:6px 0 0">${TEST_NOTE}</p>
      <div class="banner" style="margin-top:16px">ボタンとして登録できます。</div>
      <label for="slug">エンティティID</label>
      <div class="idrow"><span class="prefix">button.switchbot_</span>
        <input id="slug" placeholder="tv_power" autocomplete="off" autocapitalize="off" spellcheck="false" maxlength="40"></div>
      <div class="err" id="slugErr"></div>
      <p class="hint">「機器_操作」の形で入力します(例 tv_power、aircon_cool_26)。</p>
      <div id="aliasRow"><label for="alias">アクション名称</label>
        <p class="note" style="margin:0 0 6px">ダッシュボードの登録時に表示される名称、アイコン、エリアを以下に入力してください。</p>
        <input id="alias" placeholder="テレビ 電源" maxlength="80"></div>
      <div id="regIconSlot" class="pick"></div><div id="regAreaSlot" class="pick"></div>
      <div class="row" style="margin-top:16px"><button class="primary" data-act="register">ボタンを追加</button></div>`;
    this._sec("secRemote", html);
    this._applyTypeUi(MAIN_IDS);
    const slot = this.shadowRoot.getElementById("regIconSlot");
    if (slot) this._iconField(slot, this.s.regIcon, (v) => { this.s.regIcon = v; });
    const aslot = this.shadowRoot.getElementById("regAreaSlot");
    if (aslot) this._areaField(aslot, this.s.regArea, (v) => { this.s.regArea = v; });
  }

  _cmdText(s) {
    return s.command_type === "command"
      ? `コマンド ${s.command}${s.parameter && s.parameter !== "default" ? `(${s.parameter})` : ""}`
      : `ボタン「${s.command}」`;
  }

  _renderList() {
    const { buttons, buttonsErr } = this.s;
    let html = `<h2>登録済みのボタン</h2>`;
    if (buttonsErr) {
      html += `<div class="banner warn">${esc(buttonsErr)}</div>`;
    } else if (!buttons.length) {
      html += `<p class="empty">まだボタンがありません。リモコンを選んでボタンを登録すると、ここに並びます。</p>`;
    } else {
      html += `<ul class="list">${buttons.map((s) => `<li>
        <ha-icon icon="${esc(s.icon || "mdi:remote")}"></ha-icon>
        <div class="main"><div class="name">${esc(s.alias)}</div>
          <div class="sub meta"><span>${esc(s.entity_id)}</span><span>${esc(s.label || (s.device_id ? `リモコンID ${s.device_id.slice(0, 12)}…(一覧にありません)` : ""))}</span><span>${esc(this._cmdText(s))}</span></div>
          ${s.device_id && s.command ? "" : `<div class="sub warn">ボタン情報を読み取れません</div>`}
          </div>
        <div class="actions"><button data-act="sendButton" data-key="${esc(s.key)}">送信</button>
          <button data-act="editButton" data-key="${esc(s.key)}">編集</button>
          <button class="danger" data-act="deleteButton" data-key="${esc(s.key)}">削除</button></div></li>`).join("")}</ul>`;
    }
    this._sec("secList", html);
  }

  // ----------------------------------------------------------------- modals

  _openModal(m) { this.s.modal = m; this._renderModal(); }

  _closeModal() {
    this.s.modal = null;
    this._renderModal();
  }

  _remoteOptions(selected) {
    const { remotes } = this.s;
    const known = remotes.some((x) => x.device_id === selected);
    return (known ? "" : `<option value="${esc(selected)}" selected>${esc(selected)}(一覧にありません)</option>`) +
      remotes.map((x) => `<option value="${esc(x.device_id)}"${x.device_id === selected ? " selected" : ""}>${esc(x.label)}</option>`).join("");
  }

  _renderModal() {
    const el = this.shadowRoot.getElementById("modal");
    const m = this.s.modal;
    if (!m) { el.innerHTML = ""; return; }
    let inner = "";
    if (m.type === "cred") {
      inner = `<h3>トークンとシークレットの設定</h3>
        <p class="hint">SwitchBotアプリ(プロフィール → 設定 → アプリバージョンを10回タップ → 開発者向けオプション)で確認できる、トークンとシークレットキーを入力してください。リセットした場合は、新しい値を入力します。保存前に、クラウドで有効かどうかを確認します。</p>
        <label for="tok">トークン</label>
        <input id="tok" type="password" placeholder="${m.configured ? "変更する場合のみ入力" : ""}" autocomplete="off" spellcheck="false">
        <label for="sec">シークレット</label>
        <input id="sec" type="password" placeholder="${m.configured ? "変更する場合のみ入力" : ""}" autocomplete="off" spellcheck="false">
        <div class="actions"><button data-act="modalClose">キャンセル</button><button class="primary" data-act="modalSaveCred">保存</button></div>`;
    } else if (m.type === "editButton") {
      inner = `<h3>${esc(m.entity_id)} を編集</h3>
        <p class="hint">エンティティIDの変更は、HAの「設定 → デバイスとサービス → エンティティ」から行ってください。</p>
        <div id="eAliasRow"><label for="eAlias">アクション名称</label>
          <p class="note" style="margin:0 0 6px">ダッシュボードの登録時に表示される名称、アイコン、エリアを以下に入力してください。</p>
          <input id="eAlias" value="${esc(m.alias)}" maxlength="80"></div>
        <div id="eIconSlot" class="pick"></div><div id="eAreaSlot" class="pick"></div>
        <label for="eRemote">送信先のリモコン</label><select id="eRemote">${this._remoteOptions(m.device_id)}</select>
        <label for="eType">種別</label><select id="eType">${this._typeOptions(m.command_type)}</select>
        <label for="eCmd" id="eCmdLabel">ボタン名</label>
        <input id="eCmd" value="${esc(m.command)}" maxlength="80" autocomplete="off" spellcheck="false">
        <p class="hint" id="eCmdHint"></p>
        <div id="eParamRow"><label for="eParam">パラメータ(任意)</label>
          <input id="eParam" value="${esc(m.parameter && m.parameter !== "default" ? m.parameter : "")}" placeholder="default" maxlength="200" autocomplete="off" spellcheck="false"></div>
        <div class="row" style="margin-top:12px"><button data-act="modalTestSel">このボタンをテスト送信</button></div>
        <p class="note" id="eTestNote" style="margin:6px 0 0">${TEST_NOTE}</p>
        <div class="actions"><button data-act="modalClose">キャンセル</button><button class="primary" data-act="modalSaveButton">保存</button></div>`;
    } else if (m.type === "deleteButton") {
      inner = `<h3>削除の確認</h3><p>${esc(m.entity_id)}(${esc(m.alias)})を削除します。</p>
        <div id="refsBox">${this._refsHtml(m.refs)}</div>
        <p class="hint">このボタンのエンティティも、あわせて削除されます。</p>
        <div class="actions"><button data-act="modalClose">キャンセル</button><button class="danger" data-act="modalConfirmDelete">削除する</button></div>`;
    }
    el.innerHTML = `<div class="backdrop" data-act="modalBackdrop"><div class="dialog" role="dialog" aria-modal="true">${inner}</div></div>`;
    if (m.type === "editButton") {
      this._iconField(this.shadowRoot.getElementById("eIconSlot"), m.icon, (v) => { m.icon = v; });
      this._areaField(this.shadowRoot.getElementById("eAreaSlot"), m.area_id, (v) => { m.area_id = v; });
      this._applyTypeUi(EDIT_IDS);
    }
  }

  _openRef(remoteType) { this.s.ref = { remoteType: remoteType || "" }; this._renderRef(); }

  _closeRef() { this.s.ref = null; this._renderRef(); }

  _renderRef() {
    const el = this.shadowRoot.getElementById("refModal");
    const r = this.s.ref;
    if (!r) { el.innerHTML = ""; return; }
    const raw = r.remoteType || "";
    const isDiy = /^DIY\s/.test(raw);
    const rt = raw.replace(/^DIY\s+/, "");
    const matched = (g) => {
      if (!raw) return false;
      if (g.types.includes("*")) return rt !== "Others" && !isDiy;
      if (g.id === "others") return rt === "Others" || isDiy;
      return g.types.includes(rt);
    };
    const groups = [...CMD_GROUPS].sort((a, b) => Number(matched(b)) - Number(matched(a)));
    const body = groups.map((g) => `<div class="refgroup">
        <div class="refhead"><b>${esc(g.title)}</b>${matched(g) ? `<span class="tag">選択中のリモコンに該当</span>` : ""}</div>
        ${g.rows.length ? `<div class="scroll"><table class="reftable"><tbody>${g.rows.map((row) => `<tr>
          <td><code>${esc(row[0])}</code></td><td>${esc(row[1])}</td><td>${esc(row[2])}</td>
          <td><button data-act="useCmd" data-cmd="${esc(row[0])}" data-param="${esc(row[3] || "")}">使う</button></td></tr>`).join("")}</tbody></table></div>` : ""}
        ${g.note ? `<p class="note" style="margin:6px 0 0">${esc(g.note)}</p>` : ""}</div>`).join("");
    el.innerHTML = `<div class="backdrop" data-act="refBackdrop"><div class="dialog wide" role="dialog" aria-modal="true">
      <h3>標準コマンド一覧</h3>
      <p class="note">コマンド名は、大文字小文字も区別されます。「使う」を押すと、コマンド名が「ボタン名」の欄に(パラメータの例があれば、パラメータの欄にも)入ります。パラメータが default のものは、空欄のままで構いません。</p>
      <p class="note">SwitchBotアプリで作成したカスタムボタンは、リモコンの種類にかかわらず、種別を「カスタムボタン」にして、ボタン名を入力します(標準コマンドでは動きません)。</p>
      ${body}
      <p class="note" style="margin-top:16px">出典: <a href="${REF_URL}" target="_blank" rel="noopener noreferrer">SwitchBot API 公式ドキュメント(赤外線リモコン)</a></p>
      <div class="actions"><button class="primary" data-act="refClose">閉じる</button></div></div></div>`;
  }

  _refsHtml(refs) {
    if (refs === null) return `<p class="hint">参照を確認中…</p>`;
    if (!refs.length) return `<p class="hint">他の設定からの参照は見つかりませんでした。</p>`;
    return `<div class="banner warn">次の場所から参照されています。削除すると動かなくなります。
      <ul class="refs">${refs.map((r) => `<li>${esc(r.file)} の ${r.line} 行目: ${esc(r.text)}</li>`).join("")}</ul></div>`;
  }

  _syncButtonModal() {
    const m = this.s.modal;
    if (!m || m.type !== "editButton") return;
    m.device_id = this._q("eRemote") || m.device_id;
    m.command_type = this._q("eType") || m.command_type;
    m.alias = this._q("eAlias");
    m.command = this._q("eCmd");
    m.parameter = this._q("eParam") || "default";
  }

  // ----------------------------------------------------------------- events

  _onChange(e) {
    if (e.target.id === "remSel") {
      this.s.sel = e.target.value;
      this.s.regIcon = ""; this.s.regArea = "";
      this.s.aliasTouched = false;
      this._renderRemote();
    } else if (e.target.id === "cmdType") {
      this._applyTypeUi(MAIN_IDS);
    } else if (e.target.id === "eType") {
      this._applyTypeUi(EDIT_IDS);
    }
  }

  _onInput(e) {
    const id = e.target.id;
    if (id === "alias") { this.s.aliasTouched = true; return; }
    if (id === "cmd") {
      this._autoAlias();
      return;
    }
    if (id !== "slug") return;
    const v = e.target.value;
    const ok = v === "" || SLUG_RE.test(v);
    this.shadowRoot.getElementById("slugErr").textContent = ok ? "" : "小文字英数字とアンダースコアのみ、40文字以内で入力してください";
    e.target.classList.toggle("invalid", !ok);
  }

  // アクション名称を手入力していなければ、「リモコン名 ボタン名」を自動で入れる
  _autoAlias() {
    if (this.s.aliasTouched || this._q("cmdType") !== "customize") return;
    const cur = this.s.remotes.find((x) => x.device_id === this.s.sel);
    const alias = this.shadowRoot.getElementById("alias");
    if (cur && alias) alias.value = [cur.name, this._q("cmd")].filter(Boolean).join(" ");
  }

  _formValues() {
    return {
      device_id: this.s.sel,
      command_type: this._q("cmdType"),
      command: this._q("cmd"),
      parameter: this._q("param") || "default",
    };
  }

  _onClick(e) {
    const t = e.target.closest("[data-act]");
    if (!t) return;
    const act = t.dataset.act;
    if (t.tagName === "A") e.preventDefault();
    if (act === "refBackdrop") {
      if (e.target === t) this._closeRef();
      return;
    }
    if (act === "modalBackdrop") {
      if (e.target === t) this._closeModal();
      return;
    }
    const key = t.dataset.key;
    const s = this.s;
    const handlers = {
      fetch: () => this._work(async () => {
        s.st = await this._api("POST", "fetch", {});
        await this._loadRemotes();
        this._renderCloud();
        this._toast(`赤外線リモコンの一覧を取得しました(${s.st.count}台)`);
      }),
      cmdRef: () => {
        const editing = s.modal && s.modal.type === "editButton";
        const id = editing ? (this._q("eRemote") || s.modal.device_id) : s.sel;
        const remote = s.remotes.find((x) => x.device_id === id);
        this._openRef(remote ? remote.remote_type : "");
      },
      refClose: () => this._closeRef(),
      useCmd: () => {
        const cmd = t.dataset.cmd || "";
        const param = t.dataset.param || "";
        const put = (id, v) => { const el = this.shadowRoot.getElementById(id); if (el) el.value = v; };
        if (s.modal && s.modal.type === "editButton") { put("eCmd", cmd); put("eParam", param); }
        else { put("cmd", cmd); put("param", param); this._autoAlias(); }
        this._closeRef();
      },
      editCred: () => this._openModal({ type: "cred", configured: !!(s.st && s.st.configured) }),
      modalClose: () => this._closeModal(),
      modalSaveCred: () => this._work(async () => {
        const token = this._q("tok");
        const secret = this._q("sec");
        if (!token && !secret && !(s.st && s.st.configured)) {
          this._toast("トークンとシークレットを入力してください", "error");
          return;
        }
        s.st = await this._api("PUT", "credentials", { token, secret });
        this._closeModal();
        this._renderCloud();
        await this._loadRemotes();
        this._toast("保存しました。リモコンの一覧が古い場合は「情報を取得」を押してください");
      }),
      testSend: () => this._work(async () => {
        await this._api("POST", "test_send", this._formValues());
        this._toast("テスト送信しました");
      }),
      register: () => this._work(async () => {
        const slug = this._q("slug");
        if (!SLUG_RE.test(slug)) {
          this._toast("エンティティIDは小文字英数字とアンダースコアで入力してください", "error");
          return;
        }
        const alias = this._q("alias");
        const r = await this._api("POST", "buttons", {
          ...this._formValues(), slug, alias, icon: s.regIcon, area_id: s.regArea,
        });
        s.regIcon = ""; s.regArea = "";
        s.aliasTouched = false;
        await this._loadButtons();
        await this._loadRemotes();
        this._toast(`${r.entity_id} を追加しました`);
      }),
      sendButton: () => this._work(async () => {
        await this._api("POST", `buttons/${encodeURIComponent(key)}/send`, {});
        this._toast("送信しました");
      }),
      editButton: () => {
        const sc = s.buttons.find((x) => x.key === key);
        if (sc) this._openModal({
          type: "editButton", key, entity_id: sc.entity_id, alias: sc.alias, icon: sc.icon, area_id: sc.area_id || "",
          device_id: sc.device_id, command_type: sc.command_type, command: sc.command, parameter: sc.parameter,
        });
      },
      modalTestSel: () => this._work(async () => {
        this._syncButtonModal();
        const m = s.modal;
        await this._api("POST", "test_send", {
          device_id: m.device_id, command_type: m.command_type, command: m.command, parameter: m.parameter,
        });
        this._toast("このボタンを送信しました");
      }),
      modalSaveButton: () => this._work(async () => {
        this._syncButtonModal();
        const m = s.modal;
        await this._api("PUT", `buttons/${encodeURIComponent(m.key)}`, {
          alias: m.alias, icon: m.icon || "", area_id: m.area_id || "", device_id: m.device_id,
          command_type: m.command_type, command: m.command, parameter: m.parameter,
        });
        this._closeModal();
        await this._loadButtons();
        await this._loadRemotes();
        this._toast(`${m.entity_id} を保存しました`);
      }),
      deleteButton: () => {
        const sc = s.buttons.find((x) => x.key === key);
        if (!sc) return;
        this._openModal({ type: "deleteButton", key, entity_id: sc.entity_id, alias: sc.alias, refs: null });
        this._api("GET", `buttons/${encodeURIComponent(key)}/references`).then((r) => {
          if (!s.modal || s.modal.key !== key) return;
          s.modal.refs = r.references;
          const box = this.shadowRoot.getElementById("refsBox");
          if (box) box.innerHTML = this._refsHtml(r.references);
        }).catch((err) => this._toast(err.message, "error"));
      },
      modalConfirmDelete: () => this._work(async () => {
        const m = s.modal;
        const r = await this._api("DELETE", `buttons/${encodeURIComponent(m.key)}`);
        this._closeModal();
        await this._loadButtons();
        await this._loadRemotes();
        this._toast(`${m.entity_id} を削除しました` + (r.entity === "removed" ? "\nエンティティも削除しました。" : ""));
      }),
    };
    const fn = handlers[act];
    if (fn) fn();
  }
}

customElements.define("switchbot-ir-panel", SwitchBotIrPanel);
