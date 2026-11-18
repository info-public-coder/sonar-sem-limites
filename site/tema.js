/* Sonar Sem Limites - interface comum das paginas.

   1. Tema: o site abre SEMPRE no claro. O interruptor no canto superior
      direito liga o modo escuro, e a escolha fica lembrada neste navegador.
      Roda no <head> para nao piscar a cor errada ao abrir a pagina.
   2. Logo ampliado: tocar no logo abre a imagem grande (como foto de perfil
      nas redes sociais). Fecha pelo X, pela tecla Esc ou tocando fora dela. */
(function () {
  "use strict";
  var raiz = document.documentElement;
  var CHAVE = "sonar-tema";

  function ler() { try { return localStorage.getItem(CHAVE) === "escuro"; } catch (e) { return false; } }
  function gravar(escuro) { try { localStorage.setItem(CHAVE, escuro ? "escuro" : "claro"); } catch (e) { /* sem armazenamento */ } }
  function aplicar(escuro) {
    if (escuro) raiz.setAttribute("data-theme", "dark");
    else raiz.setAttribute("data-theme", "light");
  }
  try { localStorage.removeItem("radar-tema"); } catch (e) { /* nome antigo do site */ }
  var escuro = ler();
  aplicar(escuro);

  function interruptor() {
    var b = document.createElement("button");
    b.type = "button";
    b.className = "interruptor";
    b.setAttribute("role", "switch");
    b.innerHTML = '<span class="ic" aria-hidden="true">☀</span><span class="trilho" aria-hidden="true"><span class="bola"></span></span>' +
      '<span class="ic" aria-hidden="true">☾</span><span class="rotulo-tema">Modo escuro</span>';
    function marcar() {
      b.setAttribute("aria-checked", String(escuro));
      b.title = escuro ? "Voltar para o modo claro" : "Ligar o modo escuro";
    }
    b.addEventListener("click", function () {
      escuro = !escuro;
      aplicar(escuro); gravar(escuro); marcar();
    });
    marcar();
    return b;
  }

  function logoAmpliado() {
    var botao = document.querySelector(".logo-botao");
    if (!botao || typeof HTMLDialogElement === "undefined") return;
    var d = document.createElement("dialog");
    d.className = "foto-grande";
    d.setAttribute("aria-label", "Logo do Sonar Sem Limites ampliado");
    d.innerHTML = '<button type="button" class="fechar" aria-label="Fechar">×</button>' +
      '<img src="img/logo-512.png" width="512" height="512" alt="Logo do Sonar Sem Limites: o Bauruzinho num submarino, ' +
      'em cima de um ônibus alagado, com a inscrição Bauru - SP">' +
      '<p>Sonar Sem Limites · Bauru-SP</p>';
    document.body.appendChild(d);
    botao.addEventListener("click", function () { d.showModal(); });
    d.querySelector(".fechar").addEventListener("click", function () { d.close(); });
    // toque fora da imagem (no fundo escurecido) fecha
    d.addEventListener("click", function (e) { if (e.target === d) d.close(); });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var topo = document.querySelector(".topo");
    var vivo = document.getElementById("vivo");
    if (topo && vivo) {
      var caixa = document.createElement("div");
      caixa.className = "topo-dir";
      topo.replaceChild(caixa, vivo);
      caixa.appendChild(interruptor());
      caixa.appendChild(vivo);
    }
    logoAmpliado();
  });
})();
