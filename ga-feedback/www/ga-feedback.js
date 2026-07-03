/* GA Feedback Tool v3 — standalone bookmarklet version for any local web page */
(function(){
    // Cleanup any existing ga-feedback UI before creating fresh
    var oldIds = ['gafb-p','gafb-dialog','gafb-overlay','gafb-b','gafb-list','gafb-close','gafb-send','gafb-dialog-txt','gafb-element-note'];
    oldIds.forEach(function(id) {
        var el = document.getElementById(id);
        if (el) el.remove();
    });
    document.querySelectorAll('style').forEach(function(s) {
        if (s.textContent && s.textContent.indexOf('gafb-') >= 0) s.remove();
    });
    
    if (window.__gaFeedbackInjected) return;
    window.__gaFeedbackInjected = true;

    var API = 'http://localhost:9876/api/feedback';
    var fbs = [];  // collection list

    // ── Styles ──
    var STYLE = '\
#gafb-b{position:fixed;z-index:2147483647;bottom:20px;right:20px;width:40px;height:40px;border-radius:50%;background:#1a73e8;color:#fff;border:none;cursor:pointer;font-size:18px;box-shadow:0 2px 10px rgba(0,0,0,0.3);transition:transform .2s}\
#gafb-b:hover{transform:scale(1.15)}\
#gafb-p{position:fixed;z-index:2147483647;bottom:72px;right:20px;width:380px;max-height:70vh;background:#fff;color:#333;border-radius:12px;box-shadow:0 4px 24px rgba(0,0,0,0.25);display:none;flex-direction:column;font:14px/1.5 -apple-system,sans-serif}\
#gafb-p .hdr{padding:12px 16px;border-bottom:1px solid #e8e8e8;font-weight:600;display:flex;justify-content:space-between;align-items:center}\
#gafb-p .hdr-close{cursor:pointer;font-size:18px;opacity:.5}\
#gafb-p .hdr-close:hover{opacity:1}\
#gafb-p .body{padding:12px 16px;flex:1;overflow-y:auto}\
#gafb-p .list{max-height:320px;overflow-y:auto;margin-bottom:12px}\
#gafb-p .list-item{padding:8px 10px;margin:4px 0;background:#f5f5f5;border-radius:6px;font-size:13px;display:flex;justify-content:space-between;align-items:flex-start;word-break:break-word}\
#gafb-p .list-item .del{cursor:pointer;color:#e53935;font-size:16px;margin-left:8px;flex-shrink:0}\
#gafb-p .tools{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px}\
#gafb-p .tools button{flex:1;padding:8px 12px;border:1px solid #d0d0d0;border-radius:6px;background:#fafafa;cursor:pointer;font-size:13px;min-width:80px}\
#gafb-p .tools button.act{background:#1a73e8;color:#fff;border-color:#1a73e8}\
#gafb-p .send-btn{width:100%;padding:10px;background:#1a73e8;color:#fff;border:none;border-radius:8px;cursor:pointer;font-size:14px;font-weight:600;margin-top:4px}\
#gafb-p .send-btn:hover{background:#1557b0}\
#gafb-p .send-btn:disabled{background:#ccc;cursor:default}\
#gafb-p .note{font-size:12px;color:#888;margin-top:8px;text-align:center}\
#gafb-overlay{position:fixed;z-index:2147483646;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.08);display:none}\
.gafb-highlight{outline:3px solid #1a73e8!important;outline-offset:2px!important;background:rgba(26,115,232,0.08)!important}\
#gafb-overlay{pointer-events:none}\
.gafb-text-hl{background:#fff3cd!important;cursor:pointer}\
#gafb-dialog{position:fixed;z-index:2147483647;top:50%;left:50%;transform:translate(-50%,-50%);background:#fff;border-radius:12px;box-shadow:0 8px 32px rgba(0,0,0,0.3);padding:20px;width:400px;display:none}\
#gafb-dialog textarea{width:100%;height:80px;border:1px solid #d0d0d0;border-radius:6px;padding:8px;font:14px/1.5 sans-serif;resize:vertical;box-sizing:border-box}\
#gafb-dialog .btns{display:flex;gap:8px;margin-top:10px;justify-content:flex-end}\
#gafb-dialog .btns button{padding:6px 16px;border-radius:6px;cursor:pointer;font-size:13px}\
#gafb-dialog .btns .ok{background:#1a73e8;color:#fff;border:none}\
#gafb-dialog .btns .ok:hover{background:#1557b0}\
#gafb-dialog .btns .cancel{background:#f5f5f5;border:1px solid #d0d0d0}\
#gafb-dialog .btns .cancel:hover{background:#eee}\
.gafb-mode-off{opacity:.6;pointer-events:none}\
';

    // ── UI creation ──
    function init() {
        var s = document.createElement('style');
        s.textContent = STYLE;
        document.head.appendChild(s);

        var overlay = document.createElement('div'); overlay.id = 'gafb-overlay';
        document.body.appendChild(overlay);

        var btn = document.createElement('button'); btn.id = 'gafb-b'; btn.textContent = '📝';
        btn.onclick = function(){ togglePanel(); };
        document.body.appendChild(btn);

        var dialog = document.createElement('div'); dialog.id = 'gafb-dialog';
        dialog.innerHTML = '<div style="font-weight:600;margin-bottom:8px">你的修改意见</div><textarea id="gafb-dialog-txt" placeholder="描述你想改什么..."></textarea><div class="btns"><button class="cancel" id="gafb-dlg-cancel">取消</button><button class="ok" id="gafb-dlg-ok">提交</button></div>';
        document.body.appendChild(dialog);

        var panel = document.createElement('div'); panel.id = 'gafb-p';
        panel.innerHTML = '<div class="hdr"><span>📝 GA 反馈工具</span><span class="hdr-close" id="gafb-close">✕</span></div><div class="body"><div class="tools"><button id="gafb-pick-el">🔲 框选元素</button><button id="gafb-pick-txt">📎 选择文本</button></div><div class="list" id="gafb-list"></div><button class="send-btn" id="gafb-send" disabled>📤 发送反馈</button><div class="note">框选元素后输入意见，收集多条后统一发送</div></div>';
        document.body.appendChild(panel);

        // Events
        document.getElementById('gafb-close').onclick = function(){ hidePanel(); };
        document.getElementById('gafb-pick-el').onclick = function(){ startPicker(); };
        document.getElementById('gafb-pick-txt').onclick = function(){ startTextPicker(); };
        document.getElementById('gafb-send').onclick = function(){ sendAll(); };
        document.getElementById('gafb-dlg-cancel').onclick = function(){ hideDialog(); clearModes(); };
        document.getElementById('gafb-dlg-ok').onclick = function(){ submitDialog(); };

        renderList();
    }

    function togglePanel() {
        var p = document.getElementById('gafb-p');
        p.style.display = p.style.display === 'flex' ? 'none' : 'flex';
    }
    function hidePanel() {
        document.getElementById('gafb-p').style.display = 'none';
    }

    // ── List rendering ──
    function renderList() {
        var list = document.getElementById('gafb-list');
        if (!list) return;
        if (fbs.length === 0) {
            list.innerHTML = '<div style="color:#999;font-size:13px;padding:8px 0">暂无反馈</div>';
            document.getElementById('gafb-send').disabled = true;
            return;
        }
        document.getElementById('gafb-send').disabled = false;
        list.innerHTML = fbs.map(function(fb, i){
            var info = fb.tag ? '<' + fb.tag + (fb.id ? '#'+fb.id : '') + (fb.classes ? '.'+fb.classes.split(' ').slice(0,3).join('.') : '') + '>' : (fb.text ? '"'+fb.text.slice(0,30)+'..."' : '');
            return '<div class="list-item"><span><b>#'+(i+1)+'</b> '+info+'<br><span style="color:#555">'+escHtml(fb.note||'')+'</span></span><span class="del" data-idx="'+i+'">✕</span></div>';
        }).join('');
        list.querySelectorAll('.del').forEach(function(el){
            el.onclick = function(){
                var idx = parseInt(this.getAttribute('data-idx'));
                fbs.splice(idx,1);
                renderList();
            };
        });
    }

    function escHtml(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

    // ── Element Picker ──
    var pickerActive = false, txtPickerActive = false;
    var curTarget = null;

    function startPicker() {
        stopTextPicker(); stopPicker();
        var btn = document.getElementById('gafb-pick-el');
        btn.classList.add('act');
        document.getElementById('gafb-overlay').style.display = 'block';
        pickerActive = true;
        document.querySelectorAll('.gafb-highlight').forEach(function(e){ e.classList.remove('gafb-highlight'); });
        document.addEventListener('mouseover', pickerHover, true);
        document.addEventListener('click', pickerClick, true);
        document.getElementById('gafb-overlay').onclick = function(){ clearModes(); };
        toast('点击页面元素选择');
    }

    function stopPicker() {
        pickerActive = false;
        document.getElementById('gafb-pick-el').classList.remove('act');
        document.getElementById('gafb-overlay').style.display = 'none';
        document.querySelectorAll('.gafb-highlight').forEach(function(e){ e.classList.remove('gafb-highlight'); });
        document.removeEventListener('mouseover', pickerHover, true);
        document.removeEventListener('click', pickerClick, true);
    }

    function pickerHover(e) {
        document.querySelectorAll('.gafb-highlight').forEach(function(el){ if(el!==e.target) el.classList.remove('gafb-highlight'); });
        e.target.classList.add('gafb-highlight');
    }

    function pickerClick(e) {
        e.preventDefault(); e.stopPropagation();
        curTarget = e.target;
        showDialog('element');
    }

    // ── Text Picker ──
    function startTextPicker() {
        stopPicker(); stopTextPicker();
        document.getElementById('gafb-pick-txt').classList.add('act');
        txtPickerActive = true;
        toast('选中一段文字，然后点击文字');
        document.addEventListener('mouseup', textSelectHandler, true);
        document.addEventListener('click', textClickHandler, true);
    }

    var _selectedText = '';

    function textSelectHandler(e) {
        var sel = window.getSelection();
        _selectedText = sel ? sel.toString().trim() : '';
    }

    function textClickHandler(e) {
        if (!_selectedText) return;
        e.preventDefault(); e.stopPropagation();
        var targetEl = e.target.nodeType === 3 ? e.target.parentElement : e.target;
        curTarget = { text: _selectedText, xpath: getXPath(targetEl) };
        showDialog('text');
    }

    function stopTextPicker() {
        txtPickerActive = false;
        document.getElementById('gafb-pick-txt').classList.remove('act');
        document.removeEventListener('mouseup', textSelectHandler, true);
        document.removeEventListener('click', textClickHandler, true);
        _selectedText = '';
    }

    function clearModes() {
        stopPicker(); stopTextPicker();
        document.getElementById('gafb-overlay').style.display = 'none';
        document.querySelectorAll('.gafb-highlight').forEach(function(e){ e.classList.remove('gafb-highlight'); });
    }

    // ── Dialog ──
    function showDialog(type) {
        stopPicker(); stopTextPicker();
        document.getElementById('gafb-overlay').style.display = 'block';
        document.getElementById('gafb-dialog').style.display = 'block';
        document.getElementById('gafb-dialog-txt').value = '';
        document.getElementById('gafb-dialog-txt').focus();
        document.getElementById('gafb-dialog').dataset.type = type;
    }

    function hideDialog() {
        document.getElementById('gafb-dialog').style.display = 'none';
        curTarget = null;
    }

    function submitDialog() {
        var note = document.getElementById('gafb-dialog-txt').value.trim();
        if (!note) { toast('请填写修改意见'); return; }
        var type = document.getElementById('gafb-dialog').dataset.type;
        var fb = { type: type, note: note, time: Date.now() };
        if (type === 'element' && curTarget) {
            var el = curTarget;
            fb.tag = el.tagName ? el.tagName.toLowerCase() : '';
            fb.id = el.id || '';
            fb.classes = (el.className && typeof el.className === 'string') ? el.className : '';
            fb.text = (el.textContent||'').trim().slice(0,100);
            fb.xpath = getXPath(el);
        } else if (type === 'text') {
            fb.text = _selectedText;
            fb.xpath = curTarget ? curTarget.xpath : '';
        }
        fbs.push(fb);
        hideDialog();
        clearModes();
        renderList();
        toast('✅ 已收集 (共' + fbs.length + '条)');
    }

    // ── Send ──
    function sendAll() {
        if (fbs.length === 0) return;
        var btn = document.getElementById('gafb-send');
        btn.disabled = true;
        btn.textContent = '⏳ 发送中...';
        var payload = { feedbacks: fbs, url: location.href, title: document.title, time: Date.now() };
        // Use JSONP (script tag) — works cross-origin, no CORS restrictions
        var cb_name = 'gafb_cb_' + Date.now();
        var payload_enc = encodeURIComponent(JSON.stringify(payload));
        // Safety timer: reset button after 15s no matter what
        var safety = setTimeout(function() {
            btn.disabled = false;
            btn.textContent = '❌ 请求超时';
            btn.disabled = false;
            btn.textContent = '📤 发送反馈';
        }, 15000);
        window[cb_name] = function(data) {
            clearTimeout(safety);
            try {
                if (data && data.ok) {
                    fbs = [];
                    renderList();
                    toast('✅ 反馈已发送');
                    hidePanel();
                } else {
                    toast('❌ 发送失败: ' + JSON.stringify(data));
                    btn.disabled = false;
                    btn.textContent = '📤 发送反馈';
                }
            } finally {
                btn.disabled = false;
                btn.textContent = '📤 发送反馈';
                // Clean up
                try { delete window[cb_name]; } catch(e) {}
                var s = document.querySelector('script[src*="' + cb_name + '"]');
                if (s) s.remove();
            }
        };
        var s = document.createElement('script');
        s.src = API.replace('/api/feedback', '/api/submit') + '?callback=' + cb_name + '&data=' + payload_enc;
        s.onerror = function() {
            clearTimeout(safety);
            btn.disabled = false;
            btn.textContent = '📤 发送反馈';
            toast('❌ 无法连接服务器');
            try { delete window[cb_name]; } catch(e) {}
            s.remove();
        };
        document.body.appendChild(s);
    }

    // ── Helpers ──
    function getXPath(el) {
        if (!el || el.nodeType !== 1) return '';
        if (el.id) return '//*[@id="' + el.id + '"]';
        var parts = [];
        while (el && el.nodeType === 1) {
            var idx = 1;
            var sib = el.previousSibling;
            while (sib) { if (sib.nodeType===1 && sib.tagName===el.tagName) idx++; sib=sib.previousSibling; }
            parts.unshift(el.tagName.toLowerCase() + '[' + idx + ']');
            el = el.parentNode;
        }
        return '/' + parts.join('/');
    }

    function toast(msg) {
        var t = document.createElement('div');
        t.style.cssText = 'position:fixed;z-index:2147483647;bottom:72px;left:50%;transform:translateX(-50%);background:#333;color:#fff;padding:8px 16px;border-radius:8px;font:13px/1.4 sans-serif;box-shadow:0 2px 8px rgba(0,0,0,0.3);pointer-events:none;animation:fadeIn 0.2s';
        t.textContent = msg;
        document.body.appendChild(t);
        setTimeout(function(){ t.style.opacity='0'; t.style.transition='opacity 0.5s'; setTimeout(function(){ t.remove(); },500); }, 2500);
    }

    // ── Init ──
    init();
})();
