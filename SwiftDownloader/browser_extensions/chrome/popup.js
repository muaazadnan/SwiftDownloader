document.addEventListener("DOMContentLoaded", () => {
  const dot = document.getElementById("statusDot");
  const statusText = document.getElementById("statusText");
  const toggleBtn = document.getElementById("toggleBtn");
  const urlInput = document.getElementById("urlInput");
  const sendBtn = document.getElementById("sendBtn");

  function updateUI(status) {
    if (status.enabled) {
      dot.className = "dot on";
      statusText.textContent = "Active — intercepting downloads";
      toggleBtn.textContent = "Disable";
      toggleBtn.className = "toggle-btn";
    } else {
      dot.className = "dot off";
      statusText.textContent = "Disabled";
      toggleBtn.textContent = "Enable";
      toggleBtn.className = "toggle-btn off";
    }
  }

  // Get initial status
  chrome.runtime.sendMessage({ action: "getStatus" }, updateUI);

  // Toggle
  toggleBtn.addEventListener("click", () => {
    chrome.runtime.sendMessage({ action: "toggle" }, updateUI);
  });

  // Manual URL send
  sendBtn.addEventListener("click", () => {
    const url = urlInput.value.trim();
    if (url && (url.startsWith("http://") || url.startsWith("https://"))) {
      chrome.runtime.sendMessage({
        action: "downloadUrl",
        url: url,
      }, (resp) => {
        if (resp && resp.success) {
          urlInput.value = "";
          statusText.textContent = "URL sent!";
          setTimeout(() => {
            chrome.runtime.sendMessage({ action: "getStatus" }, updateUI);
          }, 2000);
        }
      });
    }
  });
});
