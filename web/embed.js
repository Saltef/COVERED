/* Covered embed widget.
 *
 * One script tag drops the benefits screener into any host page. It renders inside a
 * Shadow DOM so the host's CSS can never bleed in or out, reads its config from the
 * script tag's data- attributes, and calls the public /v1/eligibility API with a
 * partner key. No framework, no build step.
 *
 *   <script src="https://covered.example/static/embed.js"
 *           data-covered-key="demo-partner-key"
 *           data-brand="#c94a10"
 *           data-prefill='{"age":72,"prescription_costs_annual":2200}'></script>
 *
 * The host can pre-fill anything it already knows (age, meds, province) so the person
 * answers only what is left. Voice lives in Covered's own app; the embed is a short form.
 */
(function () {
  "use strict";
  var self = document.currentScript;
  if (!self) return;

  var KEY = self.getAttribute("data-covered-key") || "";
  var BRAND = self.getAttribute("data-brand") || "#c94a10";
  var API = (self.getAttribute("data-api") || new URL(self.src).origin).replace(/\/$/, "");
  var MOUNT = self.getAttribute("data-mount");
  var PREFILL = {};
  try { PREFILL = JSON.parse(self.getAttribute("data-prefill") || "{}"); } catch (e) {}

  // Where to render: an explicit container, or a div inserted right after this script.
  var host = MOUNT ? document.querySelector(MOUNT) : null;
  if (!host) { host = document.createElement("div"); self.parentNode.insertBefore(host, self.nextSibling); }
  var root = host.attachShadow ? host.attachShadow({ mode: "open" }) : host;

  var money = function (n) { return "$" + Number(n || 0).toLocaleString(); };

  var FIELDS = [
    { k: "age", label: "Age", type: "number", ph: "e.g. 72" },
    { k: "province", label: "Province", type: "select",
      opts: ["ON", "BC", "AB", "MB", "NB", "NL", "NS", "PE", "QC", "SK", "NT", "NU", "YT"] },
    { k: "marital_status", label: "Marital status", type: "select",
      opts: ["single", "married", "common_law", "widowed", "separated", "divorced"] },
    { k: "annual_net_income", label: "Net income (yearly)", type: "number", ph: "e.g. 24000" },
    { k: "prescription_costs_annual", label: "Prescription costs (yearly)", type: "number", ph: "e.g. 2200" },
    { k: "out_of_pocket_medical_annual", label: "Other medical costs (yearly)", type: "number", ph: "e.g. 600" },
    { k: "has_private_dental_insurance", label: "Has private dental insurance", type: "bool" },
    { k: "has_severe_prolonged_impairment", label: "Has a severe, prolonged impairment", type: "bool" },
    { k: "is_caregiver", label: "Cares for a dependant", type: "bool" }
  ];

  var css =
    ":host{all:initial}" +
    "*{box-sizing:border-box;font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif}" +
    ".w{--b:" + BRAND + ";border:1px solid #f0d9c7;border-radius:14px;background:#fff;" +
      "box-shadow:0 2px 14px rgba(154,52,18,.09);overflow:hidden;color:#1a1510;max-width:520px}" +
    ".hd{background:var(--b);color:#fff;padding:14px 18px}" +
    ".hd .t{font-weight:800;font-size:17px}.hd .s{font-size:13px;opacity:.9;margin-top:2px}" +
    ".bd{padding:16px 18px}" +
    ".row{margin:0 0 12px}label{display:block;font-size:13px;font-weight:650;color:#6b5d52;margin:0 0 5px}" +
    "input,select{width:100%;font:inherit;font-size:15px;padding:9px 11px;border:1px solid #e7d8ca;" +
      "border-radius:9px;background:#fffdfb;color:#1a1510}" +
    "input:focus,select:focus{outline:2px solid var(--b);border-color:var(--b)}" +
    ".chk{display:flex;align-items:center;gap:9px;font-size:15px;font-weight:600;color:#1a1510;cursor:pointer}" +
    ".chk input{width:20px;height:20px;accent-color:var(--b);flex:0 0 auto}" +
    ".btn{width:100%;font:inherit;font-weight:700;font-size:16px;border:none;border-radius:10px;" +
      "background:var(--b);color:#fff;padding:12px;cursor:pointer;margin-top:4px}" +
    ".btn:disabled{opacity:.55;cursor:default}" +
    ".res{padding:4px 18px 18px}.head{font-size:17px;font-weight:800;line-height:1.35;margin:8px 0 4px}" +
    ".head b{color:var(--b)}" +
    ".p{border:1px solid #f0d9c7;border-radius:11px;padding:12px 14px;margin:10px 0}" +
    ".p .tp{display:flex;justify-content:space-between;gap:10px;align-items:baseline;flex-wrap:wrap}" +
    ".p .nm{font-weight:700;font-size:15px}.p .vl{font-weight:800;color:var(--b);white-space:nowrap}" +
    ".pill{font-size:11px;font-weight:800;padding:2px 9px;border-radius:99px;text-transform:capitalize;margin-left:6px}" +
    ".pill.eligible,.pill.likely{background:#e4f6ea;color:#15803d}" +
    ".pill.maybe{background:#fdefdc;color:#b45309}.pill.not_eligible{background:#f0eeec;color:#6b6b6b}" +
    ".why{color:#4a4038;font-size:13px;margin:7px 0 0}" +
    ".unlock{font-size:11px;color:var(--b);font-weight:800;margin-left:4px}" +
    ".foot{font-size:11px;color:#8a7d72;margin-top:12px;line-height:1.4}" +
    ".err{color:#b42318;font-size:14px;padding:4px 0}" +
    ".by{font-size:11px;color:#8a7d72;text-align:right;padding:8px 18px;border-top:1px solid #f6ebe2}" +
    ".by b{color:var(--b)}" +
    "a{color:var(--b)}";

  function h(tag, attrs, html) {
    var el = document.createElement(tag);
    if (attrs) for (var k in attrs) el.setAttribute(k, attrs[k]);
    if (html != null) el.innerHTML = html;
    return el;
  }

  var wrap = h("div", { class: "w" });
  wrap.appendChild(h("div", { class: "hd" },
    "<div class='t'>Benefits you may be owed</div>" +
    "<div class='s'>A 30-second check, powered by Covered</div>"));
  var body = h("div", { class: "bd" });
  wrap.appendChild(body);
  wrap.appendChild(h("div", { class: "by" }, "Secured &amp; screened by <b>Covered</b>"));
  var style = h("style"); style.textContent = css;
  root.appendChild(style); root.appendChild(wrap);

  // ---- form ----
  function renderForm() {
    body.className = "bd"; body.innerHTML = "";
    FIELDS.forEach(function (f) {
      var pre = PREFILL[f.k];
      var row = h("div", { class: "row" });
      if (f.type === "bool") {
        var lab = h("label", { class: "chk" });
        var cb = h("input", { type: "checkbox", id: "f_" + f.k });
        if (pre === true) cb.checked = true;
        lab.appendChild(cb); lab.appendChild(document.createTextNode(" " + f.label));
        row.appendChild(lab);
      } else if (f.type === "select") {
        row.appendChild(h("label", null, f.label));
        var sel = h("select", { id: "f_" + f.k });
        f.opts.forEach(function (o) {
          var op = h("option", { value: o }, o.replace(/_/g, " "));
          if (String(pre) === o) op.setAttribute("selected", "");
          sel.appendChild(op);
        });
        row.appendChild(sel);
      } else {
        row.appendChild(h("label", null, f.label));
        var inp = h("input", { type: "number", id: "f_" + f.k, placeholder: f.ph || "", min: "0" });
        if (pre != null) inp.value = pre;
        row.appendChild(inp);
      }
      body.appendChild(row);
    });
    var btn = h("button", { class: "btn" }, "See my benefits");
    btn.addEventListener("click", submit);
    body.appendChild(btn);
    body.appendChild(h("div", { class: "err", id: "err" }));
  }

  function collect() {
    var p = {};
    FIELDS.forEach(function (f) {
      var el = root.getElementById("f_" + f.k);
      if (!el) return;
      if (f.type === "bool") p[f.k] = el.checked;
      else if (f.type === "number") p[f.k] = Number(el.value || 0);
      else p[f.k] = el.value;
    });
    return p;
  }

  function submit() {
    var btn = root.querySelector(".btn"); if (btn) { btn.disabled = true; btn.textContent = "Checking..."; }
    root.getElementById("err").textContent = "";
    fetch(API + "/v1/eligibility", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Covered-Key": KEY },
      body: JSON.stringify(collect())
    }).then(function (r) {
      if (!r.ok) throw new Error(r.status === 401 ? "This widget is not authorized." : "Could not reach Covered.");
      return r.json();
    }).then(renderResults).catch(function (e) {
      if (btn) { btn.disabled = false; btn.textContent = "See my benefits"; }
      root.getElementById("err").textContent = e.message || "Something went wrong.";
    });
  }

  function renderResults(data) {
    body.className = "res"; body.innerHTML = "";
    var n = data.programs_claimable || 0;
    body.appendChild(h("div", { class: "head" },
      "You could be owed about <b>" + money(data.total_estimated_annual) + "/yr</b> across " +
      n + " program" + (n === 1 ? "" : "s") + "."));
    (data.programs || []).forEach(function (r) {
      if (r.eligibility === "not_eligible") return;
      var val = r.estimated_annual_value ? money(r.estimated_annual_value) + "/yr" : "";
      var unlock = r.unlocked_by ? "<span class='unlock'>unlocked by " + String(r.unlocked_by).toUpperCase() + "</span>" : "";
      var p = h("div", { class: "p" },
        "<div class='tp'><span class='nm'>" + r.name +
        "<span class='pill " + r.eligibility + "'>" + r.eligibility.replace(/_/g, " ") + "</span>" + unlock +
        "</span><span class='vl'>" + val + "</span></div>" +
        "<p class='why'>" + ((r.reasons && r.reasons[0]) || "") + "</p>");
      body.appendChild(p);
    });
    body.appendChild(h("div", { class: "foot" }, data.disclaimer || ""));
    var again = h("button", { class: "btn" }, "Start over");
    again.addEventListener("click", renderForm);
    body.appendChild(again);
  }

  if (!KEY) { body.innerHTML = "<div class='err'>Covered embed: missing data-covered-key.</div>"; return; }
  renderForm();
})();
