/* Keep the newest message in view after opening a conversation. */
(() => {
  const thread = document.getElementById('message-thread');
  if (thread) thread.scrollTop = thread.scrollHeight;
})();
