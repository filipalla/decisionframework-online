/* Black Friday banner for decisionframework.online.
   Teaser from 20 Nov, live offer 27-30 Nov 2026 (Brussels time), gone afterwards. Add ?bf=1 to any page to preview the live banner. */
(function(){
  var now = Date.now(), q = /[?&]bf=1/.test(location.search);
  var TEASE = Date.UTC(2026,10,19,23,0), START = Date.UTC(2026,10,26,23,0), END = Date.UTC(2026,10,30,23,0);
  if (!q && (now < TEASE || now >= END)) return;
  var live = q || now >= START;
  var css = '#bfbar{position:relative;z-index:50;background:linear-gradient(90deg,#000,#2a2112 40%,#000);border-bottom:3px solid #e2c887;color:#f1eadb;font:15px/1.4 Arial,Helvetica,sans-serif;text-align:center;padding:14px 16px}'+
    '#bfbar .b{display:inline-block;margin:0 10px 6px 0;padding:4px 12px;background:#e2c887;color:#111214;font:bold 12px Arial;letter-spacing:.18em;text-transform:uppercase}'+
    '#bfbar s{color:#9f988b}#bfbar strong{color:#e2c887;font-size:1.15em}#bfbar code{font:bold 1.05em "Courier New",monospace;background:#e2c887;color:#111214;padding:2px 8px;margin:0 4px}'+
    '#bfbar a.go{display:inline-block;margin:8px 0 0 10px;padding:10px 20px;background:#e2c887;color:#111214;text-decoration:none;font:bold 14px Arial;letter-spacing:.1em;text-transform:uppercase}'+
    '#bfbar .t{display:block;margin-top:6px;font-size:12.5px;color:#cfc6b0}';
  var st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);
  var bar = document.createElement('div'); bar.id = 'bfbar'; bar.setAttribute('role','region'); bar.setAttribute('aria-label','Black Friday offer');
  if (live) {
    bar.innerHTML = '<span class="b">Black Friday</span>The desk for 12 months: <s>&euro;199</s> <strong>&euro;144</strong> with code <code>BLACKFRIDAY</code>'+
      '<a class="go" href="https://payhip.com/b/yz6ei">Get 12 months &rarr;</a><span class="t" id="bft"></span>';
  } else {
    bar.innerHTML = '<span class="b">Coming 27&ndash;30 Nov</span>Black Friday on the desk: the founding rate, <strong>&euro;144 for 12 months</strong>, open to everyone for four days.'+
      '<a class="go" href="https://decisionframework.online/private-client.html#desk-access">See the desk &rarr;</a>';
  }
  document.body.insertBefore(bar, document.body.firstChild);
  if (live) {
    var t = document.getElementById('bft');
    (function tick(){
      var ms = Math.max(0, END - Date.now()), d = Math.floor(ms/864e5), h = Math.floor(ms%864e5/36e5), m = Math.floor(ms%36e5/6e4);
      t.textContent = q && Date.now() < START ? 'Preview: the offer runs Fri 27 Nov to Mon 30 Nov, Brussels time.' : 'Ends Monday 30 November, midnight Brussels: ' + d + 'd ' + h + 'h ' + m + 'm left. Enter the code at checkout.';
      setTimeout(tick, 30000);
    })();
  }
})();
