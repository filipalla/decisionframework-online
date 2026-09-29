/* DecisionFramework article comments. Inactive until DF_COMMENTS_API is set. */
(function () {
  var API = 'https://flat-firefly-4a1ddf-comments.filipallaert.workers.dev';          // e.g. https://df-comments.yourname.workers.dev
  var TURNSTILE_SITEKEY = '';                    // optional Cloudflare Turnstile site key
  if (!API || API.indexOf('REPLACE_') === 0) return;
  var host = document.getElementById('df-comments'); if (!host) return;
  var page = host.getAttribute('data-page') || location.pathname.replace(/^\/|\.html$/g, '').replace(/[^a-z0-9-]/gi, '').toLowerCase();

  var css = '#df-comments{margin:56px 0 0}#df-comments h2{margin-top:0}.dfc-list{margin:18px 0 28px}.dfc{padding:16px 18px;margin:0 0 12px;background:var(--surface,#1b1b1d);border:1px solid var(--line,rgba(198,161,91,.45))}.dfc.r{margin-left:28px;border-left:3px solid var(--gold,#c6a15b)}.dfc .m{font:12.5px Arial,sans-serif;color:var(--muted,#b8b0a1);margin-bottom:6px}.dfc .m b{color:var(--text,#f1eadb);font-weight:400;font-size:14px}.dfc .a{display:inline-block;margin-left:6px;padding:1px 7px;background:var(--light,#e2c887);color:#17120a;font:11px Arial,sans-serif;letter-spacing:.06em;text-transform:uppercase}.dfc .t{color:var(--text,#f1eadb);white-space:pre-wrap;word-wrap:break-word}.dfc .rp{background:none;border:0;padding:0;margin-top:8px;color:var(--light,#e2c887);font:12px Arial,sans-serif;letter-spacing:.08em;text-transform:uppercase;cursor:pointer}.dfc-form{padding:24px;background:var(--surface,#1b1b1d);border:1px solid var(--line,rgba(198,161,91,.45))}.dfc-form h3{margin:0 0 6px;font-weight:400;color:var(--light,#e2c887)}.dfc-form p{margin:0 0 14px;font:13.5px/1.6 Arial,sans-serif}.dfc-form input,.dfc-form textarea{width:100%;box-sizing:border-box;margin:0 0 10px;padding:12px 13px;background:var(--bg,#111214);color:var(--text,#f1eadb);border:1px solid var(--line,rgba(198,161,91,.45));font:15px Arial,sans-serif}.dfc-form textarea{min-height:120px;resize:vertical}.dfc-row{display:flex;gap:10px;flex-wrap:wrap}.dfc-row input{flex:1 1 220px}.dfc-form button{padding:12px 22px;background:rgba(198,161,91,.14);color:var(--light,#e2c887);border:1px solid var(--light,#e2c887);font:15px Arial,sans-serif;cursor:pointer}.dfc-form button:hover{background:var(--light,#e2c887);color:#17120a}.dfc-msg{margin:12px 0 0;font:14.5px/1.6 Arial,sans-serif;color:var(--light,#e2c887)}.dfc-hp{position:absolute;left:-9999px}.dfc-replying{font:13px Arial,sans-serif;color:var(--muted,#b8b0a1);margin-bottom:10px}.dfc-replying button{background:none;border:0;color:var(--light,#e2c887);cursor:pointer;font:13px Arial}';
  var st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);

  function esc(s) { var d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
  function when(s) { try { return new Date(s.replace(' ', 'T') + 'Z').toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }); } catch (e) { return ''; } }

  host.innerHTML = '<h2>Discussion</h2><div class="dfc-list" aria-live="polite"></div>' +
    '<form class="dfc-form" novalidate><h3>Join the discussion</h3>' +
    '<p>Comments are open to newsletter subscribers and are published after a quick check. Your email is only used to confirm your subscription and is never shown.</p>' +
    '<div class="dfc-replying" hidden>Replying to <b></b> <button type="button">cancel</button></div>' +
    '<div class="dfc-row"><input name="name" placeholder="Your name" maxlength="60" required autocomplete="name"><input name="email" type="email" placeholder="Email you subscribed with" required autocomplete="email"></div>' +
    '<textarea name="body" placeholder="Your comment" maxlength="3000" required></textarea>' +
    '<input class="dfc-hp" name="website" tabindex="-1" autocomplete="off" aria-hidden="true">' +
    (TURNSTILE_SITEKEY ? '<div class="cf-turnstile" data-sitekey="' + TURNSTILE_SITEKEY + '" data-theme="dark" style="margin-bottom:10px"></div>' : '') +
    '<button type="submit">Post comment</button><p class="dfc-msg" role="status"></p></form>';
  if (TURNSTILE_SITEKEY) { var ts = document.createElement('script'); ts.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js'; ts.async = true; document.head.appendChild(ts); }

  var list = host.querySelector('.dfc-list'), form = host.querySelector('form'), msg = host.querySelector('.dfc-msg');
  var replyBox = host.querySelector('.dfc-replying'), parentId = null;

  function render(items) {
    if (!items.length) { list.innerHTML = '<p style="font:14px Arial,sans-serif">No comments yet. Be the first.</p>'; return; }
    var top = items.filter(function (c) { return !c.parent_id; });
    list.innerHTML = top.map(function (c) {
      var kids = items.filter(function (k) { return k.parent_id === c.id; });
      return one(c, false) + kids.map(function (k) { return one(k, true); }).join('');
    }).join('');
  }
  function one(c, reply) {
    return '<div class="dfc' + (reply ? ' r' : '') + '"><div class="m"><b>' + esc(c.name) + '</b>' + (c.is_author ? '<span class="a">Author</span>' : '') + ' &middot; ' + when(c.created_at) + '</div><div class="t">' + esc(c.body) + '</div>' +
      (reply ? '' : '<button class="rp" data-id="' + c.id + '" data-name="' + esc(c.name) + '">Reply</button>') + '</div>';
  }
  function load() {
    fetch(API + '/comments?page=' + encodeURIComponent(page)).then(function (r) { return r.json(); })
      .then(function (d) { render(d.comments || []); }).catch(function () { list.innerHTML = ''; });
  }
  list.addEventListener('click', function (e) {
    var b = e.target.closest('.rp'); if (!b) return;
    parentId = b.getAttribute('data-id'); replyBox.hidden = false; replyBox.querySelector('b').textContent = b.getAttribute('data-name');
    form.scrollIntoView({ behavior: 'smooth', block: 'center' }); form.body.focus();
  });
  replyBox.querySelector('button').addEventListener('click', function () { parentId = null; replyBox.hidden = true; });
  form.addEventListener('submit', function (e) {
    e.preventDefault(); msg.textContent = '';
    var btn = form.querySelector('button[type=submit]'); btn.disabled = true;
    var tok = form.querySelector('[name="cf-turnstile-response"]');
    fetch(API + '/comments', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ page: page, parent_id: parentId, name: form.name.value, email: form.email.value, body: form.body.value, website: form.website.value, turnstile: tok ? tok.value : '' }) })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        btn.disabled = false;
        if (d.ok) { form.body.value = ''; parentId = null; replyBox.hidden = true; msg.textContent = 'Thank you. Your comment will appear once it has been reviewed.'; }
        else {
          msg.textContent = d.error || 'Something went wrong. Please try again.';
          if (d.subscribe) { var s = document.getElementById('signup'); msg.innerHTML = esc(msg.textContent) + ' <a href="' + (s ? '#signup' : '/free-preview.html') + '">Subscribe here</a>.'; }
        }
        if (window.turnstile) try { window.turnstile.reset(); } catch (x) {}
      })
      .catch(function () { btn.disabled = false; msg.textContent = 'Connection problem. Please try again in a moment.'; });
  });
  load();
})();
