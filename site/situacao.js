window.SITUACAO = {"gerado_em":"2026-11-18T19:27","itens":[{"pagina":"Câmara","fonte":"Câmara (SAPL)","situacao":"aviso","data":"2026-11-13","detalhe":"última coleta boa há 4 dias"},{"pagina":"Câmara","fonte":"Vereadores em exercício","situacao":"ok","data":"2026-11-13","detalhe":"21 de 21"},{"pagina":"Câmara","fonte":"Fotos e votos (TSE 2024)","situacao":"ok","data":null,"detalhe":"todos com foto"},{"pagina":"Dinheiro","fonte":"TCE-SP 2026 (pagamentos do mês)","situacao":"aviso","data":"2026-11-14","detalhe":"última coleta boa há 4 dias; janeiro a 09/2026"},{"pagina":"Dinheiro","fonte":"TCE-SP 2025 (ano fechado)","situacao":"ok","data":null,"detalhe":"arquivo anual presente"},{"pagina":"Dinheiro","fonte":"PNCP Contratos 2025","situacao":"ok","data":"2026-11-14","detalhe":"coletada há 4 dia(s); 5562 registros"},{"pagina":"Dinheiro","fonte":"PNCP Contratos 2026","situacao":"aviso","data":"2026-11-14","detalhe":"última coleta boa há 4 dias; 4940 registros"},{"pagina":"Dinheiro","fonte":"PNCP Dispensa 2025","situacao":"ok","data":"2026-11-14","detalhe":"coletada há 4 dia(s); 54 registros"},{"pagina":"Dinheiro","fonte":"PNCP Dispensa 2026","situacao":"aviso","data":"2026-11-14","detalhe":"última coleta boa há 4 dias; 30 registros"},{"pagina":"Dinheiro","fonte":"PNCP Inexigibilidade 2025","situacao":"ok","data":"2026-11-14","detalhe":"coletada há 4 dia(s); 80 registros"},{"pagina":"Dinheiro","fonte":"PNCP Inexigibilidade 2026","situacao":"aviso","data":"2026-11-14","detalhe":"última coleta boa há 4 dias; 50 registros"},{"pagina":"Prefeitura","fonte":"Equipe de governo (site da Prefeitura)","situacao":"ok","data":"2026-11-14","detalhe":"coletada há 4 dia(s); só atualiza pelo computador local (o site recusa o GitHub)"},{"pagina":"Diretoria de Ensino","fonte":"Equipe (site da URE)","situacao":"ok","data":"2026-11-18","detalhe":"coletada hoje"},{"pagina":"Diretoria de Ensino","fonte":"Servidores da sede (cadastro)","situacao":"ok","data":"2026-11-18","detalhe":"conferida hoje; baixada em 18/11, fonte sem mudança desde então; só atualiza pelo computador local (o portal recusa o GitHub)"},{"pagina":"Diretoria de Ensino","fonte":"Salários (folha do Estado)","situacao":"ok","data":"2026-11-18","detalhe":"conferida hoje; baixada em 18/11, fonte sem mudança desde então"},{"pagina":"Diretoria de Ensino","fonte":"Pagamentos e diárias","situacao":"ok","data":"2026-11-18","detalhe":"conferida hoje; baixada em 18/11, fonte sem mudança desde então; só atualiza pelo computador local (o portal recusa o GitHub)"},{"pagina":"Diretoria de Ensino","fonte":"Contratos (PNCP)","situacao":"ok","data":"2026-11-18","detalhe":"coletada hoje"},{"pagina":"Diretoria de Ensino","fonte":"Folha do Estado: publicação","situacao":"aviso","data":"2026-05-11","detalhe":"o Estado não publica folha nova há 191 dias (atraso da fonte, não da coleta)"}],"falhas":0,"avisos":6};

(function () {
  var S = window.SITUACAO; if (!S) return;
  var arq = (location.pathname.split("/").pop() || "index.html").replace(/\?.*$/, "");
  var PAG = {"index.html": ["Câmara"], "": ["Câmara"], "prefeitura.html": ["Prefeitura", "Câmara"],
             "dinheiro.html": ["Dinheiro"], "diretoria.html": ["Diretoria de Ensino"]};
  var quer = PAG[arq] || ["Câmara"];
  var itens = S.itens.filter(function (i) { return quer.indexOf(i.pagina) >= 0; });
  if (!itens.length) return;
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]; }); }
  function br(d) { if (!d) return "—"; var p = d.split("-"); return p[2] + "/" + p[1] + "/" + p[0]; }
  var ROT = {ok: "em dia", aviso: "atenção", falha: "desatualizado"};
  var sec = document.createElement("section");
  sec.id = "situacao";
  sec.innerHTML = '<h2>Situação dos dados</h2><p class="sub">Quando cada fonte desta página foi coletada pela última vez com sucesso. Conferido em ' + br(S.gerado_em.slice(0, 10)) + '.</p>' +
    '<ul class="lista">' + itens.map(function (i) {
      return '<li class="item situacao-' + i.situacao + '"><div class="meta"><span class="selo">' + ROT[i.situacao] + "</span><span>" + esc(i.fonte) + "</span><span>última coleta: " + br(i.data) + "</span></div><p class=\"pequeno\">" + esc(i.detalhe) + "</p></li>";
    }).join("") + "</ul>";
  var main = document.querySelector("main");
  if (main) main.appendChild(sec);
})();
