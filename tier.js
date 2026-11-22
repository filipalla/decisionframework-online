/* DecisionFramework tiers: the free Private Client sign-in prompt, site-wide.
   0 anonymous, 1 Private Client (free, email), 2 desk member, 3 owner. The desk decides the tier;
   this script only asks it (/api/client/me) and shows the right prompt:
   - homepage: a sign-in window on arrival, every visit until the visitor signs in
   - other pages: once per browsing session, a slim bar at the bottom; insight articles also get a
     banner after the opening paragraphs. The article itself always stays open (Google indexes it).
   Pages can opt out with <body data-tier-prompt="off"> (Private Client has its own form). */
(function () {
  var DESK = 'https://desk.decisionframework.online';
  var path = location.pathname.replace(/index\.html$/, '');
  var isHome = path === '/';
  var body = document.body;
  if (!body) return;
  var optOut = body.getAttribute('data-tier-prompt') === 'off';

  var css = '' +
    '.dft-ov{position:fixed;inset:0;z-index:9999;background:rgba(8,8,10,.78);display:flex;align-items:center;justify-content:center;padding:18px}' +
    '.dft-box{position:relative;width:100%;max-width:470px;padding:34px 28px 26px;background:#17171a;border:2px solid #c6a15b;color:#f1eadb;font:16px/1.55 Georgia,serif;box-shadow:0 20px 60px rgba(0,0,0,.6)}' +
    '.dft-x{position:absolute;top:8px;right:12px;background:none;border:0;color:#b8b0a1;font:26px Arial;cursor:pointer}' +
    '.dft-badge{display:inline-block;padding:5px 12px;background:#c6a15b;color:#111214;font:700 11px Arial,sans-serif;letter-spacing:.18em;text-transform:uppercase}' +
    '.dft-h{font:400 1.75rem/1.2 Georgia,serif;margin:14px 0 8px}.dft-h em{color:#e2c887}' +
    '.dft-p{color:#b8b0a1;margin:0 0 16px;font-size:15px}' +
    '.dft-ul{margin:0 0 18px;padding-left:18px;color:#d9d1c2;font:14.5px/1.6 Arial,sans-serif}' +
    'form.dft-f{display:block;background:none;border:0;padding:0;margin:0;box-shadow:none}' +
    '.dft-f label.dft-c{display:flex;letter-spacing:0;text-transform:none}.dft-f input[type=checkbox]{width:auto;padding:0;margin:2px 0 0;flex:0 0 auto}' +
    '.dft-f input[type=email]{width:100%;padding:14px;background:#0f0f11;border:1px solid rgba(198,161,91,.45);color:#f1eadb;font:16px Arial,sans-serif;box-sizing:border-box}' +
    '.dft-f button{width:100%;margin-top:10px;padding:16px;background:linear-gradient(180deg,#d4202f,#a50f1c);color:#ffe08a;border:1px solid #e2c887;font:700 16px Arial,sans-serif;letter-spacing:.08em;text-transform:uppercase;cursor:pointer;box-shadow:0 0 0 3px rgba(212,32,47,.18)}' +
    '.dft-f button:disabled{opacity:.6;cursor:wait}' +
    '.dft-c{display:flex;gap:8px;align-items:flex-start;margin-top:12px;font:13px/1.45 Arial,sans-serif;color:#b8b0a1}.dft-c input{margin-top:2px}' +
    '.dft-m{margin:12px 0 0;font:14px/1.5 Arial,sans-serif;color:#e2c887}.dft-m.err{color:#e4a493}' +
    '.dft-fine{margin:12px 0 0;font:12px/1.5 Arial,sans-serif;color:#8f887b}.dft-fine a{color:#e2c887}' +
    '.dft-bar{position:fixed;left:0;right:0;bottom:0;z-index:9998;display:flex;flex-wrap:wrap;align-items:center;justify-content:center;gap:12px 18px;padding:12px 16px;background:#17171a;border-top:2px solid #c6a15b;color:#f1eadb;font:15px/1.4 Arial,sans-serif}' +
    '.dft-bar b{color:#e2c887}.dft-bar a.go{padding:10px 18px;background:linear-gradient(180deg,#d4202f,#a50f1c);color:#ffe08a;border:1px solid #e2c887;font:700 13px Arial;letter-spacing:.06em;text-transform:uppercase;text-decoration:none}' +
    '.dft-bar button{background:none;border:0;color:#b8b0a1;font:22px Arial;cursor:pointer}' +
    '.dft-in{margin:34px 0;padding:24px 26px;border:2px solid #c6a15b;background:linear-gradient(160deg,#2a2112,#17171a);color:#f1eadb;font:16px/1.55 Georgia,serif}' +
    '.dft-in .dft-h{font-size:1.4rem;margin-top:10px}.dft-in a.go{display:inline-block;margin-top:6px;padding:13px 22px;background:linear-gradient(180deg,#d4202f,#a50f1c);color:#ffe08a;border:1px solid #e2c887;font:700 14px Arial;letter-spacing:.06em;text-transform:uppercase;text-decoration:none}';

  function el(html) { var d = document.createElement('div'); d.innerHTML = html; return d.firstChild; }
  function addCss() { if (document.getElementById('dft-css')) return; var s = document.createElement('style'); s.id = 'dft-css'; s.textContent = css; document.head.appendChild(s); }

  // the sign-in form, used by the window, the inline banner and the Private Client page
  function formHtml(btn) {
    return '<form class="dft-f" novalidate><input type="email" name="email" autocomplete="email" placeholder="you@example.com" required aria-label="Email address">' +
      '<button type="submit">' + (btn || '&#9889; Open Private Client free') + '</button>' +
      '<label class="dft-c"><input type="checkbox" name="newsletter"> Also send me the free Sunday Weather Report by email.</label>' +
      '<p class="dft-m" role="status" aria-live="polite"></p>' +
      '<p class="dft-fine">No password: we email you a one-time sign-in link. Your email is only used to sign you in' +
      ' (and for the Weather Report if you tick the box). <a href="/disclosures.html">Disclosures</a></p></form>';
  }
  function wire(form) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var email = form.email.value.trim(), msg = form.querySelector('.dft-m'), btn = form.querySelector('button');
      msg.className = 'dft-m'; msg.textContent = '';
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) { msg.className = 'dft-m err'; msg.textContent = 'Please enter a valid email address.'; form.email.focus(); return; }
      var nl = form.newsletter.checked;
      btn.disabled = true; var old = btn.innerHTML; btn.textContent = 'Sending your link…';
      fetch(DESK + '/api/client/signup', { method: 'POST', credentials: 'include', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ email: email, newsletter: nl }) })
        .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
        .then(function (res) {
          if (!res.ok) throw new Error(res.d && res.d.error || 'error');
          if (nl) {   // newsletter only with the box ticked: the existing Kit form, with its own confirmation email
            var fd = new FormData(); fd.append('email_address', email); fd.append('fields[source]', 'private-client'); fd.append('ckjs_version', '6');
            fetch('https://app.kit.com/forms/10000249/subscriptions', { method: 'POST', body: fd, headers: { Accept: 'application/json', 'X-CKJS-Version': '6' } }).catch(function () {});
          }
          form.querySelectorAll('input,button,label').forEach(function (x) { x.style.display = 'none'; });
          msg.innerHTML = '<b>Check your inbox.</b> We sent a sign-in link to ' + email.replace(/[<>&]/g, '') + '. Click it to open Private Client. Nothing after a few minutes? Look in your spam folder.';
        })
        .catch(function (err) { btn.disabled = false; btn.innerHTML = old; msg.className = 'dft-m err'; msg.textContent = (err && err.message && err.message !== 'error') ? err.message : 'Something went wrong. Please try again in a moment.'; });
    });
  }

  function modal() {
    addCss();
    var ov = el('<div class="dft-ov" role="dialog" aria-modal="true" aria-labelledby="dft-h"><div class="dft-box">' +
      '<button class="dft-x" aria-label="Close">&times;</button><span class="dft-badge">Private Client &middot; free</span>' +
      '<div class="dft-h" id="dft-h">Open your <em>Private Client</em> access</div>' +
      '<p class="dft-p">Create your free account with just your email and get a window into the desk:</p>' +
      '<ul class="dft-ul"><li>Today&rsquo;s Asia briefing: what gold and silver did overnight</li><li>The morning Shanghai and India gold premiums</li><li>One full desk note every week</li></ul>' +
      formHtml() + '</div></div>');
    body.appendChild(ov);
    wire(ov.querySelector('form'));
    function close() { ov.remove(); document.removeEventListener('keydown', esc); }
    function esc(e) { if (e.key === 'Escape') close(); }
    ov.querySelector('.dft-x').onclick = close;
    ov.addEventListener('click', function (e) { if (e.target === ov) close(); });
    document.addEventListener('keydown', esc);
    setTimeout(function () { var i = ov.querySelector('input[type=email]'); if (i) i.focus(); }, 50);
  }
  function bar() {
    addCss();
    var b = el('<div class="dft-bar" role="region" aria-label="Private Client"><span><b>Private Client is free.</b> Today&rsquo;s Asia briefing and the morning premiums, with just your email.</span>' +
      '<a class="go" href="/private-client.html">&#9889; Open it free</a><button aria-label="Close">&times;</button></div>');
    body.appendChild(b);
    b.querySelector('button').onclick = function () { b.remove(); try { sessionStorage.setItem('dft-bar', 'closed'); } catch (e) {} };
  }
  // insight articles: a banner after the second paragraph of the article text
  function inline() {
    var art = document.querySelector('article') || document.querySelector('main');
    if (!art) return;
    var ps = art.querySelectorAll('p');
    if (ps.length < 4) return;
    addCss();
    var box = el('<aside class="dft-in" aria-label="Private Client"><span class="dft-badge">Private Client &middot; free</span>' +
      '<div class="dft-h">More of this, every morning, in <em>Private Client</em></div>' +
      '<p class="dft-p">Today&rsquo;s Asia briefing and the morning Shanghai and India premiums open free after you create your account with your email.</p>' +
      '<a class="go" href="/private-client.html">&#9889; Create your free account</a></aside>');
    ps[1].parentNode.insertBefore(box, ps[1].nextSibling);
  }

  function prompts(tier) {
    if (tier >= 1 || optOut) return;
    var article = !isHome && document.querySelector('article, [itemtype*="Article"], meta[property="og:type"][content="article"]');
    if (isHome) { modal(); return; }
    if (article) inline();
    var seen; try { seen = sessionStorage.getItem('dft-bar'); } catch (e) {}
    if (!seen) bar();
  }

  window.DFClient = { formHtml: formHtml, wire: wire, desk: DESK, addCss: addCss };
  var p = fetch(DESK + '/api/client/me', { credentials: 'include', cache: 'no-store' })
    .then(function (r) { return r.ok ? r.json() : { tier: 0 }; })
    .catch(function () { return { tier: 0 }; });
  window.DFClient.me = p;
  p.then(function (t) { document.documentElement.setAttribute('data-tier', String(t.tier || 0)); prompts(t.tier || 0); });
})();
