/* School-quiz page runtime. Plain classic script, no framework, no build step.
   Rules that keep this safe for kids:
   - quiz and UI text only ever goes in through textContent / text nodes, never innerHTML;
   - image src is set as a property, link hrefs are only built from validated values;
   - styles are only set through the CSSOM (el.style.x), never style="..." attributes (CSP). */
"use strict";

(function () {
  var LANG_KEY = "quizgen-lang";
  var REPO_URL = "https://github.com/rcocetta/school-quiz";

  // The builder guarantees complete data: every Text has all quiz languages and every
  // language has all UI strings, so there are no fallbacks for missing text below.
  var quiz = JSON.parse(document.getElementById("quiz-data").textContent);
  var uiStrings = JSON.parse(document.getElementById("ui-strings").textContent);
  var app = document.getElementById("app");

  // One object holds everything that has to survive a language switch.
  var state = {
    lang: quiz.languages[0],
    screen: "start",      // "start" | "question" | "end"
    items: [],            // this attempt: [{q, order: [original option indexes]}]
    index: 0,             // current question
    chosen: [],           // per question: original option index, or -1 if unanswered
    revealed: false       // immediate mode: has the current question been answered?
  };

  // Screen readers get feedback messages through this polite live region.
  var live = document.createElement("div");
  live.className = "sr-only";
  live.setAttribute("role", "status");
  live.setAttribute("aria-live", "polite");
  document.body.appendChild(live);

  /* ---------- small helpers ---------- */

  // Create an element. Children can be strings (become text nodes) or nodes.
  function el(tag, className) {
    var node = document.createElement(tag);
    if (className) { node.className = className; }
    for (var i = 2; i < arguments.length; i++) {
      var child = arguments[i];
      if (child === null || child === undefined || child === false) { continue; }
      node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
    }
    return node;
  }

  // Pick the text for the current language out of a {lang: string} map.
  function tr(map) {
    if (!map) { return ""; }
    return map[state.lang];
  }

  // Built-in UI string for the current language.
  function ui(key, vars) {
    return fill(uiStrings[state.lang][key], vars || {});
  }

  function message(key) {
    return uiStrings[state.lang].messages[key];
  }

  function hasOwn(obj, name) { return Object.prototype.hasOwnProperty.call(obj, name); }

  // Replace {placeholders} in a plain string.
  function fill(template, vars) {
    return template.replace(/\{(\w+)\}/g, function (m, name) {
      return hasOwn(vars, name) ? String(vars[name]) : m;
    });
  }

  // Like fill(), but a value may be a DOM node (used to turn only the name into a link).
  function fillNodes(template, vars) {
    var frag = document.createDocumentFragment();
    template.split(/(\{\w+\})/).forEach(function (part) {
      var m = /^\{(\w+)\}$/.exec(part);
      var value = m && hasOwn(vars, m[1]) ? vars[m[1]] : undefined;
      if (value === undefined) {
        if (part) { frag.appendChild(document.createTextNode(part)); }
      } else {
        frag.appendChild(typeof value === "string" ? document.createTextNode(value) : value);
      }
    });
    return frag;
  }

  function announce(text) {
    live.textContent = "";
    // Clearing first makes screen readers repeat identical messages.
    window.setTimeout(function () { live.textContent = text; }, 30);
  }

  // Fisher-Yates shuffle, returns a new array.
  function shuffled(list) {
    var a = list.slice();
    for (var i = a.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var tmp = a[i]; a[i] = a[j]; a[j] = tmp;
    }
    return a;
  }

  function correctIndex(q) {
    for (var i = 0; i < q.options.length; i++) {
      if (q.options[i].correct) { return i; }
    }
  }

  // 1-based position of an original option index as shown on screen.
  function positionOf(item, optIndex) { return item.order.indexOf(optIndex) + 1; }

  /* ---------- language ---------- */

  function loadSavedLang() {
    try {
      var saved = window.localStorage.getItem(LANG_KEY);
      if (saved && quiz.languages.indexOf(saved) !== -1) { state.lang = saved; }
    } catch (e) { /* storage blocked: the page works without it */ }
  }

  function saveLang() {
    try { window.localStorage.setItem(LANG_KEY, state.lang); } catch (e) { /* ignore */ }
  }

  function applyLangToDocument() {
    document.documentElement.setAttribute("lang", state.lang);
    document.title = tr(quiz.title);
  }

  function setLang(code) {
    if (code === state.lang) { return; }
    state.lang = code;
    saveLang();
    applyLangToDocument();
    render(".lang-btn[data-lang=\"" + code + "\"]");
  }

  function languageSwitcher() {
    if (quiz.languages.length < 2) { return null; }
    var group = el("div", "lang-switch");
    quiz.languages.forEach(function (code) {
      var strings = uiStrings[code];
      var flag = el("span", "", strings.flag);
      flag.setAttribute("aria-hidden", "true");
      var btn = el("button", "lang-btn", flag, el("span", "", code.toUpperCase()));
      btn.type = "button";
      btn.setAttribute("data-lang", code);
      btn.setAttribute("lang", code);
      btn.setAttribute("aria-label", strings.name);
      btn.setAttribute("aria-pressed", code === state.lang ? "true" : "false");
      btn.addEventListener("click", function () { setLang(code); });
      group.appendChild(btn);
    });
    var nav = el("nav", "topbar", group);
    nav.setAttribute("aria-label", ui("choose_language"));
    return nav;
  }

  /* ---------- shared pieces ---------- */

  function safeUrl(url) {
    return typeof url === "string" && /^https?:\/\//i.test(url) ? url : null;
  }

  function safeEmail(email) {
    return typeof email === "string" && /^[^\s<>?&#:]+@[^\s<>?&#:]+$/.test(email) ? email : null;
  }

  function externalLink(href, text) {
    var a = el("a", "", text);
    a.href = href;
    a.rel = "noopener noreferrer";
    // New tab so a child following a link does not lose the quiz in progress.
    if (/^https?:/i.test(href)) { a.target = "_blank"; }
    return a;
  }

  function authorLine() {
    var author = quiz.author;
    if (!author || !author.name) { return null; }
    var url = safeUrl(author.url);
    var email = safeEmail(author.email);
    var nameNode = author.name;
    if (url) { nameNode = externalLink(url, author.name); }
    else if (email) { nameNode = externalLink("mailto:" + email, author.name); }
    var p = el("p", "meta");
    p.appendChild(fillNodes(ui("made_by"), { name: nameNode }));
    return p;
  }

  // Site mode only: a link back to the index page (builder sets index_url, a relative path).
  function backLink() {
    var url = quiz.index_url;
    if (typeof url !== "string" || !url || url.indexOf(":") !== -1 || url.indexOf("//") === 0) { return null; }
    var a = el("a", "back-link", el("span", "back-arrow", "\u2190"), ui("back_to_all"));
    a.firstChild.setAttribute("aria-hidden", "true");
    a.href = url;
    return a;
  }

  function footer() {
    return el("footer", "footer", externalLink(REPO_URL, ui("made_with")));
  }

  // Accessible text for an option's image (see the contract's fallback rules).
  function optionAlt(opt, position) {
    if (opt.image_alt !== undefined && opt.image_alt !== null) { return tr(opt.image_alt); }   // "" = decorative
    if (opt.text) { return ""; }              // the text next to it already says it
    return ui("picture_n", { n: position });
  }

  function makeImage(className, src, alt) {
    var img = el("img", className);
    img.alt = alt;
    img.src = src;
    return img;
  }

  // Short inline version of an option, for the feedback panel and the review list.
  function inlineAnswer(opt, position) {
    var span = el("span", "inline-answer");
    if (opt.image) { span.appendChild(makeImage("review-img", opt.image, optionAlt(opt, position))); }
    if (opt.text) { span.appendChild(document.createTextNode(tr(opt.text))); }
    return span;
  }

  /* ---------- quiz flow ---------- */

  function startAttempt() {
    var pool = shuffled(quiz.questions);
    var count = Math.min(quiz.questions_per_quiz, pool.length);
    state.items = pool.slice(0, count).map(function (q) {
      var order = q.options.map(function (o, i) { return i; });
      return { q: q, correct: correctIndex(q), order: quiz.shuffle_options ? shuffled(order) : order };
    });
    state.chosen = state.items.map(function () { return -1; });
    state.index = 0;
    state.revealed = false;
    state.screen = "question";
    render(".js-heading");
  }

  // A tap or key press only selects (and can be changed); "Check" or "Next" confirms.
  function pick(optionIndex) {
    if (quiz.feedback === "immediate" && state.revealed) { return; }
    state.chosen[state.index] = optionIndex;
    render(".option[data-i=\"" + optionIndex + "\"]");
  }

  function check() {
    if (state.chosen[state.index] === -1 || state.revealed) { return; }
    state.revealed = true;
    render(".js-feedback");
  }

  function plainAnswer(opt, position) {
    return opt.text ? tr(opt.text) : optionAlt(opt, position);
  }

  function next() {
    if (state.chosen[state.index] === -1) { return; }
    if (state.index + 1 < state.items.length) {
      state.index += 1;
      state.revealed = false;
      render(".js-heading");
    } else {
      state.screen = "end";
      render(".js-heading");
    }
  }

  /* ---------- screens ---------- */

  function startScreen() {
    var n = Math.min(quiz.questions_per_quiz, quiz.questions.length);
    var heading = el("h1", "js-heading", tr(quiz.title));
    heading.tabIndex = -1;
    var startBtn = el("button", "btn", ui("start"));
    startBtn.type = "button";
    startBtn.addEventListener("click", startAttempt);
    var desc = quiz.description ? el("p", "lead", tr(quiz.description)) : null;
    var hero = el("section", "hero", heading, desc,
      el("p", "badge-count", ui(n === 1 ? "questions_count_one" : "questions_count", { count: n })), authorLine(), startBtn);
    return el("main", "screen", backLink(), hero);
  }

  function optionButton(item, pos) {
    var optIndex = item.order[pos];
    var opt = item.q.options[optIndex];
    var locked = quiz.feedback === "immediate" && state.revealed;
    var chosen = state.chosen[state.index];
    var isChosen = chosen === optIndex;

    var btn = el("button", "option");
    btn.type = "button";
    btn.setAttribute("data-i", String(optIndex));

    var key = el("span", "option-key", String(pos + 1));
    key.setAttribute("aria-hidden", "true");
    var body = el("span", "option-body");
    if (opt.image) { body.appendChild(makeImage("option-img", opt.image, optionAlt(opt, pos + 1))); }
    if (opt.text) { body.appendChild(el("span", "", tr(opt.text))); }
    var mark = el("span", "mark");
    mark.setAttribute("aria-hidden", "true");
    btn.appendChild(key);
    btn.appendChild(body);
    btn.appendChild(mark);

    if (locked) {
      // Icon + text for sighted users; extra words for screen readers on each button.
      btn.setAttribute("aria-disabled", "true");
      if (opt.correct) {
        btn.setAttribute("data-state", isChosen ? "right" : "reveal");
        mark.textContent = "✓";
        btn.appendChild(el("span", "sr-only", " (" + ui("correct_answer") + ")"));
      } else if (isChosen) {
        btn.setAttribute("data-state", "wrong");
        mark.textContent = "✗";
      }
      if (isChosen) { btn.appendChild(el("span", "sr-only", " (" + ui("your_answer") + ")")); }
    } else if (isChosen) {
      btn.setAttribute("data-state", "selected");
      btn.setAttribute("aria-pressed", "true");
      mark.textContent = "●";
    } else {
      btn.setAttribute("aria-pressed", "false");
    }
    if (!locked) { btn.addEventListener("click", function () { pick(optIndex); }); }
    return btn;
  }

  function feedbackPanel(item) {
    var chosen = state.chosen[state.index];
    var ok = item.q.options[chosen].correct === true;
    var icon = el("span", "feedback-icon", ok ? "✓" : "✗");
    icon.setAttribute("aria-hidden", "true");
    var body = el("div", "feedback-body", el("p", "feedback-title", ok ? ui("correct") : ui("wrong")));
    if (!ok) {
      body.appendChild(el("p", "answer-line", ui("the_answer_was") + " ",
        inlineAnswer(item.q.options[item.correct], positionOf(item, item.correct))));
    }
    if (item.q.explanation) { body.appendChild(el("p", "", tr(item.q.explanation))); }
    var panel = el("div", ok ? "feedback js-feedback" : "feedback feedback--oops js-feedback", icon, body);
    panel.tabIndex = -1;
    return panel;
  }

  function questionScreen() {
    var item = state.items[state.index];
    var total = state.items.length;
    var current = state.index + 1;

    var barFill = el("div", "progress-fill");
    barFill.style.width = Math.round((current / total) * 100) + "%";   // CSSOM: allowed by the CSP
    var bar = el("div", "progress", barFill);
    bar.setAttribute("aria-hidden", "true");
    var progress = el("p", "progress-text", ui("question_x_of_y", { current: current, total: total }));

    progress.id = "progress-text";
    var heading = el("h2", "js-heading", tr(item.q.text));
    heading.tabIndex = -1;
    heading.setAttribute("aria-describedby", "progress-text");
    var image = item.q.image ? makeImage("question-img", item.q.image, tr(item.q.image_alt)) : null;

    var allPictures = item.q.options.every(function (o) { return o.image && !o.text; });
    var list = el("div", allPictures ? "options options--pictures" : "options");
    for (var pos = 0; pos < item.order.length; pos++) { list.appendChild(optionButton(item, pos)); }

    // Hidden h1 so every page has one top heading; the question itself is the h2.
    var screen = el("main", "screen", el("h1", "sr-only", tr(quiz.title)), progress, bar, heading, image, list);

    var answered = state.chosen[state.index] !== -1;
    if (quiz.feedback === "immediate" && state.revealed) { screen.appendChild(feedbackPanel(item)); }
    var confirm = null;
    if (quiz.feedback === "immediate" && !state.revealed) {
      confirm = el("button", "btn js-check", ui("check"));
      confirm.addEventListener("click", check);
    } else {
      var last = state.index + 1 === total;
      confirm = el("button", "btn js-next", last ? ui("finish") : ui("next"));
      confirm.addEventListener("click", next);
    }
    confirm.type = "button";
    confirm.disabled = !answered;
    screen.appendChild(confirm);
    screen.appendChild(backLink());
    return screen;
  }

  function reviewItem(item, i) {
    var chosenIdx = state.chosen[i];
    var q = item.q;
    var ci = item.correct;
    var ok = chosenIdx === ci;
    var mark = el("span", "mark", ok ? "✓" : "✗");
    mark.setAttribute("aria-hidden", "true");

    var body = el("div", "review-body",
      el("p", "review-q", el("span", "sr-only", (ok ? ui("correct") : ui("wrong")) + " "), tr(q.text)));
    var mine = chosenIdx === -1 ? null : inlineAnswer(q.options[chosenIdx], positionOf(item, chosenIdx));
    body.appendChild(el("p", "review-line", el("strong", "", ui("your_answer") + ": "), mine));
    if (!ok) {
      body.appendChild(el("p", "review-line", el("strong", "", ui("correct_answer") + ": "),
        inlineAnswer(q.options[ci], positionOf(item, ci))));
    }
    if (q.explanation) { body.appendChild(el("p", "review-explain", tr(q.explanation))); }

    var li = el("li", "review-item", mark, body);
    li.setAttribute("data-ok", ok ? "true" : "false");
    return li;
  }

  function endScreen() {
    var total = state.items.length;
    var score = 0;
    state.items.forEach(function (item, i) {
      if (state.chosen[i] === item.correct) { score += 1; }
    });
    var pct = total ? score / total : 0;
    var tier = pct >= 0.8 ? "great" : pct >= 0.5 ? "good" : "keep_trying";

    var heading = el("h1", "score-label js-heading", ui("your_score"));
    heading.tabIndex = -1;
    var again = el("button", "btn", ui("try_again"));
    again.type = "button";
    again.addEventListener("click", startAttempt);
    var value = el("p", "score-value", ui("score_x_of_y", { score: score, total: total }));
    var note = el("p", "score-message", message(tier));
    value.id = "score-value";
    note.id = "score-message";
    heading.setAttribute("aria-describedby", "score-value score-message");   // heard on arrival
    var result = el("section", "result", heading, value, note, again);

    var list = el("ol", "review-list");
    state.items.forEach(function (item, i) { list.appendChild(reviewItem(item, i)); });
    return el("main", "screen", backLink(), result, el("h2", "review-title", ui("review")), list);
  }

  /* ---------- render ---------- */

  // Rebuild the whole page from state, then move focus to `focusSelector`.
  // Rebuilding is cheap and keeps the code simple: state is the only truth.
  function render(focusSelector) {
    var screen = state.screen === "question" ? questionScreen()
      : state.screen === "end" ? endScreen() : startScreen();
    var page = el("div", "page", languageSwitcher(), screen, footer());
    app.textContent = "";
    app.appendChild(page);
    var target = focusSelector && app.querySelector(focusSelector);
    if (target) { target.focus(); }
    if (focusSelector === ".js-heading") { window.scrollTo(0, 0); }
  }

  /* ---------- keyboard: number keys pick options ---------- */

  // Number keys only select, and only while focus is inside the options (WCAG 2.1.4).
  document.addEventListener("keydown", function (event) {
    if (state.screen !== "question" || event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) { return; }
    if (!(event.target && event.target.closest && event.target.closest(".options"))) { return; }
    var n = parseInt(event.key, 10);
    var item = state.items[state.index];
    if (!(n >= 1 && n <= 9) || n > item.order.length) { return; }
    if (quiz.feedback === "immediate" && state.revealed) { return; }
    event.preventDefault();
    pick(item.order[n - 1]);
  });

  loadSavedLang();
  applyLangToDocument();
  render("");
})();
