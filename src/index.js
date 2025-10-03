import React from 'react';
import ReactDOM from 'react-dom/client';
import Counter from './components/Counter';

function App() {
  return (
    <div>
      <h1>Welcome to the Mocap App</h1>
      <Counter />
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
