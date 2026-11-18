/* Radar Sem Limites - tema claro/escuro.
   Padrao: segue o sistema (prefers-color-scheme). O botao alterna
   Automatico -> Claro -> Escuro e lembra a escolha neste navegador.
   Roda no <head> para nao piscar a cor errada ao abrir a pagina. */
(function () {
  "use strict";
  var raiz = document.documentElement;
  function ler() { try { return localStorage.getItem("radar-tema") || "auto"; } catch (e) { return "auto"; } }
  function gravar(v) { try { localStorage.setItem("radar-tema", v); } catch (e) { /* navegador sem armazenamento */ } }
  function aplicar(v) {
    if (v === "claro") raiz.setAttribute("data-theme", "light");
    else if (v === "escuro") raiz.setAttribute("data-theme", "dark");
    else raiz.removeAttribute("data-theme");
  }
  var atual = ler();
  aplicar(atual);
  var ROTULO = { auto: "Tema: automático", claro: "Tema: claro", escuro: "Tema: escuro" };
  var PROXIMO = { auto: "claro", claro: "escuro", escuro: "auto" };
  document.addEventListener("DOMContentLoaded", function () {
    var topo = document.querySelector(".topo");
    var vivo = document.getElementById("vivo");
    if (!topo || !vivo) return;
    var caixa = document.createElement("div");
    caixa.className = "topo-dir";
    var botao = document.createElement("button");
    botao.type = "button";
    botao.className = "tema";
    function rotular() {
      botao.textContent = ROTULO[atual];
      botao.setAttribute("aria-label", ROTULO[atual] + ". Toque para mudar.");
    }
    botao.addEventListener("click", function () {
      atual = PROXIMO[atual];
      aplicar(atual); gravar(atual); rotular();
    });
    rotular();
    topo.replaceChild(caixa, vivo);
    caixa.appendChild(botao);
    caixa.appendChild(vivo);
  });
})();
