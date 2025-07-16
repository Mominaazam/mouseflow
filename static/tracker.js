// static/tracker.js
(function () {
  let events = [];

  const record = (type, e) => {
    console.log(type);
    
    const event = {
      type,
      timestamp: Date.now(),
      x: e.clientX || null,
      y: e.clientY || null
    };
    events.push(event);
  };

  document.addEventListener('click', e => record('click', e));
  document.addEventListener('mousemove', e => record('mousemove', e));
  
  window.addEventListener('scroll', function(e) {
    console.log('scroll', window.scrollX, window.scrollY);
    const maxScrollX = document.documentElement.scrollWidth - window.innerWidth;
    const maxScrollY = document.documentElement.scrollHeight - window.innerHeight;
    const scrollPercentX = maxScrollX > 0 ? (window.scrollX / maxScrollX) * 100 : 0;
    const scrollPercentY = maxScrollY > 0 ? (window.scrollY / maxScrollY) * 100 : 0;
    events.push({
        type: 'scroll',
        timestamp: Date.now(),
        x: Math.round(scrollPercentX * 100) / 100,
        y: Math.round(scrollPercentY * 100) / 100,
        data: null
    });
});

  setInterval(() => {
    if (events.length === 0) return;
    fetch('http://127.0.0.1:5000/collect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        events,
        url: window.location.href  // Send the current URL
      })
    }).catch(console.error);
    events = [];
  }, 10000); //1 min, 60 secs, 60000. 10000 = 10 secs
})();
