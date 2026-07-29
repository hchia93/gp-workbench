// .claude task 文档脚本：自动目录（按 h2）+ ContentTab 切换
// 需在能跑 JS 的预览查看（浏览器 / Live Preview）。
(function () {
  var heads = document.querySelectorAll('h2');
  heads.forEach(function (h, i) { if (!h.id) h.id = 'sec-' + i; });

  function titleOf(h) {
    var c = h.cloneNode(true);
    c.querySelectorAll('.badge').forEach(function (b) { b.remove(); });
    return c.textContent.trim();
  }

  var outline = document.getElementById('outline');
  if (outline) {
    var s = '<div class="o-label">目录</div>';
    heads.forEach(function (h, i) {
      s += '<a href="#' + h.id + '"><span class="o-num">' + (i + 1) + '</span> · ' + titleOf(h) + '</a>';
    });
    outline.innerHTML = s;
  }

})();

(function () {
  document.querySelectorAll('.switcher').forEach(function (sw) {
    var tabs = sw.querySelectorAll(':scope > .sw-tabs > .sw-tab');
    var panels = sw.querySelectorAll(':scope > .sw-panels > .sw-panel');
    tabs.forEach(function (tab, i) {
      tab.addEventListener('click', function () {
        tabs.forEach(function (t) { t.classList.remove('active'); });
        panels.forEach(function (p) { p.classList.remove('active'); });
        tab.classList.add('active');
        if (panels[i]) panels[i].classList.add('active');
      });
    });
  });
})();
