// app.js — capture capteurs + envoi WebSocket


(() => {
// UI elements
const serverInput = document.getElementById('serverInput');
const deviceIdInput = document.getElementById('deviceIdInput');
const intervalInput = document.getElementById('intervalInput');
const permissionBtn = document.getElementById('permissionBtn');
const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const wsStatus = document.getElementById('wsStatus');
const seqEl = document.getElementById('seq');
const lastSentEl = document.getElementById('lastSent');
const sentCountEl = document.getElementById('sentCount');
const sensorList = document.getElementById('sensorList');


// state
let ws = null;
let deviceId = null;
let seq = 0;
let sendInterval = Number(intervalInput.value) || 100;
let sendTimer = null;
let sentCount = 0;


// latest sensor readings
const sensors = {
accelerometer: null,
gyroscope: null,
rotation: null,
orientation: null,
// more (from Generic Sensor API) can be added
};


// helper: create (or use) device id
function getOrCreateDeviceId(){
const v = deviceIdInput.value.trim();
if(v) return v;
// try crypto.randomUUID
try{
const id = (crypto && crypto.randomUUID) ? crypto.randomUUID() : 'device-' + Math.random().toString(36).slice(2,10);
deviceIdInput.value = id;
return id;
}catch(e){
const id = 'device-' + Math.random().toString(36).slice(2,10);
deviceIdInput.value = id;
return id;
}
}


// UI update for sensors
function renderSensors(){
sensorList.innerHTML = '';
Object.keys(sensors).forEach(name => {
const card = document.createElement('div');
card.className = 'sensor-card';
const title = document.createElement('h3');
title.textContent = name;
const pre = document.createElement('pre');
pre.textContent = sensors[name] ? JSON.stringify(sensors[name], null, 2) : 'no data';
// render loop for UI values
if(sensors[name]){
(function update(){
pre.textContent = JSON.stringify(sensors[name], null, 2);
requestAnimationFrame(update);
})();
}
card.appendChild(title);
card.appendChild(pre);
sensorList.appendChild(card);
});
}

// update WebSocket status UI
function updateWsStatus(){
if(ws && ws.readyState === WebSocket.OPEN){
wsStatus.textContent = 'Connected';
wsStatus.style.color = 'green';
}else if(ws && ws.readyState === WebSocket.CONNECTING){
wsStatus.textContent = 'Connecting...';
wsStatus.style.color = 'orange';
}else{
wsStatus.textContent = 'Disconnected';
wsStatus.style.color = 'red';
}
}

// start WebSocket connection
function startWebSocket(){
const url = serverInput.value.trim();
if(!url){
alert('Please enter WebSocket server URL');
return;
}
ws = new WebSocket(url);
updateWsStatus();
ws.onopen = () => {
updateWsStatus();
console.log('WebSocket connected');
};
ws.onclose = () => {
updateWsStatus();
console.log('WebSocket disconnected');
};
ws.onerror = (err) => {
console.error('WebSocket error', err);
};
}
// stop WebSocket connection
function stopWebSocket(){
if(ws){
ws.close();
ws = null;
updateWsStatus();
}
}

// send sensor data via WebSocket
function sendSensorData(){
if(!ws || ws.readyState !== WebSocket.OPEN) return;
const payload = {
deviceId,
seq: seq++,
timestamp: Date.now(),
sensors
};
ws.send(JSON.stringify(payload));
lastSentEl.textContent = new Date().toLocaleTimeString();
sentCount++;
sentCountEl.textContent = sentCount;
}

// start sending data at intervals
function startSending(){
if(sendTimer) clearInterval(sendTimer);
sendTimer = setInterval(sendSensorData, sendInterval);
}

// stop sending data
function stopSending(){
if(sendTimer){
clearInterval(sendTimer);
sendTimer = null;
}
}

// request permission for motion sensors (iOS)
function requestPermission(){
if(typeof DeviceMotionEvent !== 'undefined' && typeof DeviceMotionEvent.requestPermission === 'function'){
DeviceMotionEvent.requestPermission()
.then(response => {
if(response === 'granted'){
setupSensors();
permissionBtn.style.display = 'none';
startBtn.style.display = 'inline-block';
}else{
alert('Permission denied for motion sensors');
}
})
.catch(console.error);
}else{
setupSensors();
permissionBtn.style.display = 'none';
startBtn.style.display = 'inline-block';
}
}

// setup sensor event listeners
function setupSensors(){
if('DeviceMotionEvent' in window){
window.addEventListener('devicemotion', (event) => {
sensors.accelerometer = {
x: event.acceleration.x,
y: event.acceleration.y,
z: event.acceleration.z
};
sensors.gyroscope = {
alpha: event.rotationRate.alpha,
beta: event.rotationRate.beta,
gamma: event.rotationRate.gamma
};
});
}
if('DeviceOrientationEvent' in window){
window.addEventListener('deviceorientation', (event) => {
sensors.orientation = {
alpha: event.alpha,
beta: event.beta,
gamma: event.gamma
};
});
}
// Generic Sensor API (if supported)
if('Accelerometer' in window){
try{
const accel = new Accelerometer({frequency: 60});
accel.addEventListener('reading', () => {
sensors.accelerometer = {
x: accel.x,
y: accel.y,
z: accel.z
};
});
accel.start();
}catch(e){
console.warn('Accelerometer not available', e);
}
}
if('Gyroscope' in window){
try{
const gyro = new Gyroscope({frequency: 60});
gyro.addEventListener('reading', () => {
sensors.gyroscope = {
x: gyro.x,
y: gyro.y,
z: gyro.z
};
});
gyro.start();
}catch(e){
console.warn('Gyroscope not available', e);
}
}
if('AbsoluteOrientationSensor' in window){
try{
const rotation = new AbsoluteOrientationSensor({frequency: 60});
rotation.addEventListener('reading', () => {
sensors.rotation = {
quaternion: Array.from(rotation.quaternion)
};
});
rotation.start();
}catch(e){
console.warn('AbsoluteOrientationSensor not available', e);
}
}
renderSensors();
}

// event listeners
permissionBtn.addEventListener('click', requestPermission);
startBtn.addEventListener('click', () => {
deviceId = getOrCreateDeviceId();
sendInterval = Number(intervalInput.value) || 100;
startWebSocket();
startSending();
startBtn.style.display = 'none';
stopBtn.style.display = 'inline-block';
});
stopBtn.addEventListener('click', () => {
stopSending();
stopWebSocket();
startBtn.style.display = 'inline-block';
stopBtn.style.display = 'none';
});

// initial UI state
updateWsStatus();
renderSensors();
})();