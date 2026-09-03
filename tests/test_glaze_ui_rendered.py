"""Rendered browser acceptance for the GoreeCloud Manager Django GLAZE UI V1.0 surface."""

from __future__ import annotations

import contextlib
import functools
import http.server
import shutil
import socket
import subprocess
import tempfile
import threading
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase

ROOT = Path(__file__).resolve().parents[1]
TARGET_VERSION = "1.0.0"
GLAZE_SOURCE_REVISION = "70909bbdccad378fb7281ae1842e2f5beed64c38"
SNAPSHOTS = ("overview", "tasks", "everkeep", "privacy-shield", "login")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def find_browser() -> str:
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path
    raise AssertionError("Manager GLAZE UI V1.0 rendered acceptance requires a Chromium-family browser")


def acceptance_page() -> str:
    pages = ",".join(f'"{name}"' for name in SNAPSHOTS)
    page = r'''<!doctype html>
<html lang="en" data-status="pending">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Manager GLAZE UI V1.0 rendered acceptance</title>
<style>
html,body{margin:0;padding:0;background:#fff;color:#000;font:14px system-ui,sans-serif}
iframe{display:block;width:100vw;height:1000px;border:0}
#result{position:fixed;inset:auto 0 0;z-index:9999;margin:0;padding:8px;background:#fff;color:#000;white-space:pre-wrap}
</style>
</head>
<body>
<div id="frames"></div><pre id="result">PENDING</pre>
<script>
const pages=[__PAGES__];
const params=new URLSearchParams(location.search);
const expectedTheme=params.get('theme')||'light';
const mode=params.get('mode')||'normal';
const failures=[];
const note=(ok,message)=>{if(!ok) failures.push(message)};
const durationMs=value=>Math.max(...value.split(',').map(part=>{
  const item=part.trim();
  if(item.endsWith('ms')) return parseFloat(item)||0;
  if(item.endsWith('s')) return (parseFloat(item)||0)*1000;
  return 0;
}));
function visible(element){
  const style=getComputedStyle(element);
  const rect=element.getBoundingClientRect();
  return style.display!=='none'&&style.visibility!=='hidden'&&rect.width>0&&rect.height>0;
}
function applyMode(root){
  if(mode==='touch-assistance'){
    root.dataset.glzInput='touch';
    root.dataset.glzTouchAssistance='true';
  } else if(mode==='text-200'){
    root.dataset.glzTextScale='200';
  } else if(mode==='reduced-transparency'){
    root.dataset.glzTransparency='reduced';
  } else if(mode==='increased-contrast'){
    root.dataset.mode='increased-contrast';
  }
}
function inspect(frame,name){
  const doc=frame.contentDocument;
  const win=frame.contentWindow;
  note(Boolean(doc),name+' has no contentDocument');
  if(!doc) return;
  const root=doc.documentElement;
  applyMode(root);
  const rootStyle=win.getComputedStyle(root);
  note(root.dataset.glazeUi==='1.0.0',name+' lost V1 version marker');
  note(root.dataset.glazeSourceRevision==='70909bbdccad378fb7281ae1842e2f5beed64c38',name+' lost exact canonical source revision');
  note(root.dataset.glazeConsumerStatus==='migration-in-progress',name+' overclaimed downstream acceptance');
  note(root.dataset.glzShell==='application',name+' lost Application shell classification');
  note(doc.body.classList.contains('glz1-workspace'),name+' lost V1 workspace class');
  const sheets=[...doc.querySelectorAll('link[rel=stylesheet]')].map(link=>link.getAttribute('href')||'');
  note(sheets.length>0&&sheets[sheets.length-1].includes('core/css/glaze-ui.css'),name+' does not load the V1 mapping last');
  note(rootStyle.getPropertyValue('--manager-glaze-version').trim().replaceAll('"','')==='1.0.0',name+' lost repository V1 token');
  note(rootStyle.getPropertyValue('--manager-glaze-source-revision').trim().replaceAll('"','')==='70909bbdccad378fb7281ae1842e2f5beed64c38',name+' lost source provenance token');
  note(rootStyle.getPropertyValue('--glz1-target-shell').trim()==='48px',name+' lost 48px target floor');
  note(rootStyle.getPropertyValue('--glz1-target-assisted').trim()==='56px',name+' lost 56px assisted target floor');
  if(mode==='forced-colors'){
    note(rootStyle.getPropertyValue('--glz1-canvas').trim().toLowerCase()==='canvas',name+' did not activate forced-colors Canvas semantics');
    note(rootStyle.getPropertyValue('--glz1-focus').trim().toLowerCase()==='highlight',name+' did not activate forced-colors Highlight focus semantics');
  } else {
    const expectedCanvas=expectedTheme==='dark'?'#0b0d11':'#f5f7fa';
    note(rootStyle.getPropertyValue('--glz1-canvas').trim().toLowerCase()===expectedCanvas,name+' did not activate '+expectedTheme+' V1 tokens');
  }
  if(mode==='touch-assistance'){
    note(root.dataset.glzInput==='touch',name+' did not enter touch input mode');
    note(root.dataset.glzTouchAssistance==='true',name+' did not enter Touch Assistance');
  }
  if(mode==='text-200'){
    note(root.dataset.glzTextScale==='200',name+' did not enter 200% text mode');
    note(parseFloat(rootStyle.fontSize)>=31.5,name+' root text did not reach 200% scale');
  }
  if(mode==='increased-contrast'){
    note(rootStyle.getPropertyValue('--glz1-focus-width').trim()==='4px',name+' did not strengthen focus geometry');
  }
  note(doc.documentElement.scrollWidth<=frame.clientWidth+1,name+' horizontally overflows '+frame.clientWidth+'px viewport: '+doc.documentElement.scrollWidth+'px');
  const controls=[...doc.querySelectorAll('.brand,.nav-link,.theme-toggle,.link-button,button,input:not([type=hidden]),select,textarea')].filter(visible);
  note(controls.length>0,name+' exposes no representative controls');
  const minimum=mode==='touch-assistance'?55.5:47.5;
  for(const control of controls){
    if(control.matches('textarea')) continue;
    const rect=control.getBoundingClientRect();
    note(rect.height>=minimum,name+' control below target floor: '+control.tagName+'.'+control.className+' = '+rect.height.toFixed(1)+'px');
  }
  if(mode==='reduced-motion'){
    const target=controls[0]||doc.body;
    note(durationMs(win.getComputedStyle(target).transitionDuration)<=0.1,name+' reduced-motion transition remains active');
  }
  if(mode==='reduced-transparency'){
    const header=doc.querySelector('.site-header');
    if(header&&visible(header)){
      const style=win.getComputedStyle(header);
      note(style.backdropFilter==='none'||style.webkitBackdropFilter==='none',name+' reduced transparency left backdrop filtering active');
    }
  }
}
async function run(){
  note(matchMedia('(prefers-color-scheme: '+expectedTheme+')').matches,'browser did not enter expected '+expectedTheme+' color scheme');
  if(mode==='reduced-motion') note(matchMedia('(prefers-reduced-motion: reduce)').matches,'browser did not activate reduced motion');
  if(mode==='forced-colors') note(matchMedia('(forced-colors: active)').matches,'browser did not activate forced colors');
  const host=document.getElementById('frames');
  const frames=pages.map(name=>{
    const frame=document.createElement('iframe');
    frame.dataset.page=name;
    frame.src='/'+name+'.html';
    host.appendChild(frame);
    return frame;
  });
  await Promise.all(frames.map(frame=>new Promise(resolve=>frame.addEventListener('load',resolve,{once:true}))));
  await new Promise(resolve=>setTimeout(resolve,150));
  for(const frame of frames) inspect(frame,frame.dataset.page);
  const result=document.getElementById('result');
  if(failures.length){document.documentElement.dataset.status='fail';result.textContent='FAIL\n'+failures.join('\n');}
  else{document.documentElement.dataset.status='pass';result.textContent='PASS';}
}
run();
</script>
</body></html>'''
    return page.replace("__PAGES__", pages)


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


@contextlib.contextmanager
def serve(root: Path):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    handler = functools.partial(QuietHandler, directory=str(root))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield port
    finally:
        server.shutdown()
        thread.join(timeout=5)


def browser_command(browser: str, url: str, profile: str, *, width: int, height: int, theme: str, mode: str) -> list[str]:
    command = [
        browser,
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--disable-background-networking",
        "--disable-default-apps",
        "--disable-extensions",
        "--disable-sync",
        "--no-first-run",
        "--mute-audio",
        "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=6500",
        f"--user-data-dir={profile}",
        f"--window-size={width},{height}",
    ]
    if theme == "dark":
        command.append("--force-dark-mode")
    if mode == "reduced-motion":
        command.append("--force-prefers-reduced-motion")
    elif mode == "forced-colors":
        command.append("--force-high-contrast")
    return [*command, "--dump-dom", url]


class GlazeUiRenderedTests(TestCase):
    """Exercise representative real Manager templates in a real browser engine."""

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="glaze-render", password="glaze-render-only-password")

    def _build_snapshots(self, root: Path) -> None:
        factory = RequestFactory()
        request = factory.get("/")
        request.user = self.user
        templates = {
            "overview": ("core/overview.html", {}),
            "tasks": ("core/tasks.html", {}),
            "everkeep": ("core/everkeep.html", {}),
            "privacy-shield": ("core/privacy_shield.html", {}),
            "login": ("core/login.html", {"form": AuthenticationForm()}),
        }
        for name in SNAPSHOTS:
            template, context = templates[name]
            html = render_to_string(template, context=context, request=request)
            require(f'data-glaze-ui="{TARGET_VERSION}"' in html, f"{name} lost V1 marker")
            require(f'data-glaze-source-revision="{GLAZE_SOURCE_REVISION}"' in html, f"{name} lost V1 provenance")
            (root / f"{name}.html").write_text(html, encoding="utf-8")
        shutil.copytree(ROOT / "core/static/core", root / "static/core", dirs_exist_ok=True)
        (root / "acceptance.html").write_text(acceptance_page(), encoding="utf-8")

    def _run_case(self, browser: str, port: int, *, width: int, height: int, theme: str, mode: str = "normal") -> None:
        url = f"http://127.0.0.1:{port}/acceptance.html?theme={theme}&mode={mode}"
        with tempfile.TemporaryDirectory(prefix="manager-glaze-v1-profile-") as profile:
            result = subprocess.run(
                browser_command(browser, url, profile, width=width, height=height, theme=theme, mode=mode),
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=45,
                check=False,
            )
        output = result.stdout or result.stderr
        require(result.returncode == 0, f"Chromium failed for {width}x{height} {theme} {mode}: {output[-3000:]}")
        require('data-status="pass"' in result.stdout and "PASS" in result.stdout, f"rendered acceptance failed for {width}x{height} {theme} {mode}: {output[-5000:]}")

    def test_representative_manager_surfaces_render_under_v1_contract(self):
        browser = find_browser()
        with tempfile.TemporaryDirectory(prefix="manager-glaze-v1-render-") as directory:
            root = Path(directory)
            self._build_snapshots(root)
            with serve(root) as port:
                for theme in ("light", "dark"):
                    self._run_case(browser, port, width=390, height=844, theme=theme)
                    self._run_case(browser, port, width=1280, height=900, theme=theme)
                for mode in ("reduced-motion", "forced-colors", "touch-assistance", "text-200", "reduced-transparency", "increased-contrast"):
                    self._run_case(browser, port, width=390, height=844, theme="light", mode=mode)
