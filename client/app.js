(() => {
    // ===== UI =====
    const deviceIdInput = document.getElementById('deviceIdInput');
    const intervalInput = document.getElementById('intervalInput');
    const permissionBtn = document.getElementById('permissionBtn');
    const startBtn = document.getElementById('startBtn');
    const stopBtn = document.getElementById('stopBtn');
    const wsStatus = document.getElementById('wsStatus');
    const lastSentEl = document.getElementById('lastSent');
    const sentCountEl = document.getElementById('sentCount');
    const sensorList = document.getElementById('sensorList');
  
    // ===== state =====
    let ws = null;
    let deviceId = null;
    let seq = 0;
    let sendInterval = Number(intervalInput?.value) || 100;
    let sendTimer = null;
    let sentCount = 0;
  
    // ===== latest sensor readings =====
    const sensors = { accelerometer: null, gyroscope: null, rotation: null, orientation: null };
  
    // ===== helpers =====
    function getOrCreateDeviceId() {
      const v = (deviceIdInput?.value || '').trim();
      if (v) return v;
      const id = (crypto && crypto.randomUUID) ? crypto.randomUUID() : 'device-' + Math.random().toString(36).slice(2, 10);
      if (deviceIdInput) deviceIdInput.value = id;
      return id;
    }
  
    function renderSensors() {
      if (!sensorList) return;
      sensorList.innerHTML = '';
      Object.keys(sensors).forEach(name => {
        const card = document.createElement('div');
        card.className = 'sensor-card';
        const title = document.createElement('h3');
        title.textContent = name;
        const pre = document.createElement('pre');
        pre.textContent = sensors[name] ? JSON.stringify(sensors[name], null, 2) : 'no data';
        (function update() {
          pre.textContent = sensors[name] ? JSON.stringify(sensors[name], null, 2) : 'no data';
          requestAnimationFrame(update);
        })();
        card.appendChild(title); card.appendChild(pre); sensorList.appendChild(card);
      });
    }
  
    function updateWsStatus() {
      if (!wsStatus) return;
      if (ws && ws.readyState === WebSocket.OPEN)      { wsStatus.textContent = 'Connected';   wsStatus.style.color = 'green'; }
      else if (ws && ws.readyState === WebSocket.CONNECTING) { wsStatus.textContent = 'Connecting...'; wsStatus.style.color = 'orange'; }
      else { wsStatus.textContent = 'Disconnected'; wsStatus.style.color = 'red'; }
    }
  
    function startWebSocket() {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.host;
      const wsUrl = `${protocol}//${host}/ws?client_type=source`;
      ws = new WebSocket(wsUrl);
      updateWsStatus();
      ws.onopen = () => { updateWsStatus(); console.log('WebSocket connected as SOURCE'); };
      ws.onclose = () => { updateWsStatus(); console.log('WebSocket disconnected'); };
      ws.onerror = (err) => { console.error('WebSocket error', err); };
    }
  
    function stopWebSocket() {
      if (ws) { try { ws.close(); } catch {} ws = null; updateWsStatus(); }
    }
  
    function sendSensorData() {
      if (!ws || ws.readyState !== WebSocket.OPEN) return;
      const payload = { deviceId, seq: seq++, timestamp: Date.now(), sensors };
      ws.send(JSON.stringify(payload));
      if (lastSentEl) lastSentEl.textContent = new Date().toLocaleTimeString();
      sentCount++; if (sentCountEl) sentCountEl.textContent = sentCount;
    }
  
    function startSending() {
      if (sendTimer) clearInterval(sendTimer);
      sendTimer = setInterval(sendSensorData, sendInterval);
    }
  
    function stopSending() {
      if (sendTimer) { clearInterval(sendTimer); sendTimer = null; }
    }
  
    // ===== Recorder (CSV) =====
    const iso = (t) => new Date(t).toISOString();
    const csvEscape = (s) => {
      if (s == null) return '';
      const str = String(s);
      return /[",\n]/.test(str) ? `"${str.replace(/"/g, '""')}"` : str;
    };
  
    const dataset = {
      rows: [],
      pushRow(rowObj) {
        const header = ['label','device_id','start_time_iso','duration_ms','accel','gyro','orientation','mag','gravity'];
        if (this.rows.length === 0) this.rows.push(header);
        const line = header.map(k => csvEscape(rowObj[k] ?? ''));
        this.rows.push(line);
        updateDatasetUI();
      },
      toCSVString() { return this.rows.map(r => Array.isArray(r) ? r.join(',') : r).join('\n'); },
      clear() { this.rows = []; updateDatasetUI(); }
    };
  
    function updateDatasetUI() {
      const countEl = document.getElementById('datasetCount');
      if (countEl) countEl.textContent = Math.max(0, dataset.rows.length - 1);
    }
    function setLastLabelUI(label) {
      const el = document.getElementById('lastLabel');
      if (el) el.textContent = label || '—';
    }
  
    class WindowRecorder {
      constructor() {
        this.capturing = false;
        this.active = null; // { label, t0, durationMs, buffers }
        this.deviceIdGetter = () => document.getElementById('deviceIdInput')?.value || '';
      }
      start(label, durationMs = 1000) {
        if (this.capturing) return;
        this.capturing = true;
        const t0 = performance.now();
        this.active = {
          label, t0, durationMs,
          buffers: { accel: [], gyro: [], orientation: [], mag: [], gravity: [] }
        };
        console.log(`[recorder] start "${label}" for ${durationMs}ms`);
        setTimeout(() => this.finish(), durationMs);
        setLastLabelUI(label);
      }
      ingest(sample) {
        if (!this.capturing || !this.active) return;
        const t = performance.now() - this.active.t0;
        const b = this.active.buffers;
  
        if (sample.acc)   { const { x,y,z } = sample.acc;        b.accel.push({ t, ax:x, ay:y, az:z }); }
        if (sample.gyro)  { const { x,y,z } = sample.gyro;       b.gyro.push({ t, gx:x, gy:y, gz:z }); }
        if (sample.ori)   { const { alpha,beta,gamma } = sample.ori; b.orientation.push({ t, alpha, beta, gamma }); }
        if (sample.mag)   { const { x,y,z } = sample.mag;        b.mag.push({ t, mx:x, my:y, mz:z }); }
        if (sample.gravity){ const { x,y,z } = sample.gravity;   b.gravity.push({ t, gx:x, gy:y, gz:z }); }
      }
      finish() {
        if (!this.active) return;
        const { label, durationMs, buffers } = this.active;
        console.log(`[recorder] finish "${label}"`, buffers);
        dataset.pushRow({
          label,
          device_id: this.deviceIdGetter(),
          start_time_iso: iso(Date.now()),
          duration_ms: Math.round(durationMs),
          accel: JSON.stringify(buffers.accel),
          gyro: JSON.stringify(buffers.gyro),
          orientation: JSON.stringify(buffers.orientation),
          mag: JSON.stringify(buffers.mag),
          gravity: JSON.stringify(buffers.gravity),
        });
        this.capturing = false; this.active = null;
      }
    }
    const recorder = new WindowRecorder();
  
    function bindDatasetButtons() {
      const b1 = document.getElementById('moveBtn1');
      const b2 = document.getElementById('moveBtn2');
      const b3 = document.getElementById('moveBtn3');
      const save = document.getElementById('saveCsvBtn');
      const clear = document.getElementById('clearCsvBtn');
  
      if (b1) b1.addEventListener('click', () => { recorder.start('move_1', 1000); });
      if (b2) b2.addEventListener('click', () => { recorder.start('move_2', 1000); });
      if (b3) b3.addEventListener('click', () => { recorder.start('move_3', 1000); });
  
      if (save) save.addEventListener('click', async () => {
        if (dataset.rows.length <= 1) { alert('Aucune donnée enregistrée.'); return; }
        const csv = dataset.toCSVString();
        const ts = new Date().toISOString().replace(/[:.]/g, '-');
        const fileName = `dataset_${ts}.csv`;
        try {
          const res = await fetch('/upload_csv', { method:'POST', headers:{ 'Content-Type':'text/plain' }, body: csv });
          if (res.ok) alert(`✅ CSV envoyé au serveur (${fileName})`);
          else alert(`❌ Erreur serveur : ${res.status}`);
        } catch (err) {
          alert('Erreur d’envoi: ' + err.message);
        }
      });
  
      if (clear) clear.addEventListener('click', () => {
        if (confirm('Effacer le dataset en mémoire ?')) dataset.clear();
      });
    }
  
    // ===== sensors wiring (corrigé) =====
    function setupSensors() {
      // DeviceMotion (accélération + rotationRate)
      if ('DeviceMotionEvent' in window) {
        window.addEventListener('devicemotion', (event) => {
          const a = event.acceleration || event.accelerationIncludingGravity || {};
          sensors.accelerometer = { x: a.x ?? 0, y: a.y ?? 0, z: a.z ?? 0 };
  
          const r = event.rotationRate || {};
          // MAPPING CORRIGÉ : alpha/beta/gamma -> x/y/z
          sensors.gyroscope = { x: r.alpha ?? 0, y: r.beta ?? 0, z: r.gamma ?? 0 };
  
          recorder.ingest({ acc: sensors.accelerometer, gyro: sensors.gyroscope });
        }, { passive: true });
      }
  
      // DeviceOrientation
      if ('DeviceOrientationEvent' in window) {
        window.addEventListener('deviceorientation', (event) => {
          sensors.orientation = { alpha: event.alpha ?? 0, beta: event.beta ?? 0, gamma: event.gamma ?? 0 };
          recorder.ingest({ ori: sensors.orientation });
        }, { passive: true });
      }
  
      // Generic Sensor API (si dispo)
      if ('Accelerometer' in window) {
        try {
          const accel = new Accelerometer({ frequency: 60 });
          accel.addEventListener('reading', () => {
            sensors.accelerometer = { x: accel.x, y: accel.y, z: accel.z };
            recorder.ingest({ acc: sensors.accelerometer });
          });
          accel.start();
        } catch (e) { console.warn('Accelerometer not available', e); }
      }
      if ('Gyroscope' in window) {
        try {
          const gyro = new Gyroscope({ frequency: 60 });
          gyro.addEventListener('reading', () => {
            sensors.gyroscope = { x: gyro.x, y: gyro.y, z: gyro.z };
            recorder.ingest({ gyro: sensors.gyroscope });
          });
          gyro.start();
        } catch (e) { console.warn('Gyroscope not available', e); }
      }
      if ('AbsoluteOrientationSensor' in window) {
        try {
          const rotation = new AbsoluteOrientationSensor({ frequency: 60 });
          rotation.addEventListener('reading', () => {
            sensors.rotation = { quaternion: Array.from(rotation.quaternion) };
          });
          rotation.start();
        } catch (e) { console.warn('AbsoluteOrientationSensor not available', e); }
      }
  
      renderSensors();
    }
  
    // ===== permissions + start/stop =====
    function requestPermission() {
      const needsPerm = (typeof DeviceMotionEvent !== 'undefined' && typeof DeviceMotionEvent.requestPermission === 'function')
                     || (typeof DeviceOrientationEvent !== 'undefined' && typeof DeviceOrientationEvent.requestPermission === 'function');
  
      if (needsPerm) {
        // iOS nécessite HTTPS ou localhost
        Promise.all([
          DeviceMotionEvent?.requestPermission?.().catch(() => 'denied'),
          DeviceOrientationEvent?.requestPermission?.().catch(() => 'denied')
        ]).then(([pm1, pm2]) => {
          if (pm1 === 'granted' || pm2 === 'granted') {
            setupSensors();
            if (permissionBtn) permissionBtn.style.display = 'none';
            if (startBtn) startBtn.style.display = 'inline-block';
          } else {
            alert('Permission capteurs refusée. Utilise HTTPS (ngrok) ou localhost sur l’appareil.');
          }
        }).catch(err => {
          console.error('Error requesting permission', err);
          alert('Erreur lors de la demande de permission : ' + (err?.message || String(err)));
        });
      } else {
        setupSensors();
        if (permissionBtn) permissionBtn.style.display = 'none';
        if (startBtn) startBtn.style.display = 'inline-block';
      }
    }
  
    if (permissionBtn) permissionBtn.addEventListener('click', requestPermission);
  
    if (startBtn) startBtn.addEventListener('click', () => {
      deviceId = getOrCreateDeviceId();
      sendInterval = Number(intervalInput?.value) || 100;
      startWebSocket();
      startSending();
  
      // UI
      startBtn.style.display = 'none';
      if (stopBtn) {
        stopBtn.style.display = 'inline-block';
        stopBtn.disabled = false;
        stopBtn.removeAttribute('disabled'); // important si présent dans le HTML
      }
    });
  
    if (stopBtn) stopBtn.addEventListener('click', () => {
      // en cas de styles résiduels, retire tout blocage
      stopBtn.disabled = true;
      stopBtn.setAttribute('aria-disabled', 'true');
  
      stopSending();
      stopWebSocket();
  
      // UI
      if (startBtn) startBtn.style.display = 'inline-block';
      stopBtn.style.display = 'none';
    });
  
    // ===== initial UI =====
    if (stopBtn) {
      stopBtn.disabled = true; // alignement avec l’état initial
      stopBtn.setAttribute('aria-disabled', 'true');
    }
    bindDatasetButtons();
    updateWsStatus();
    renderSensors();
  })();
  