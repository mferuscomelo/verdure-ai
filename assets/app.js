const phaseEl = document.querySelector('#phase');
const weightEl = document.querySelector('#weight');
const resultEl = document.querySelector('#result');
const errorContainer = document.querySelector('#error-container');

const PHASE_LABELS = {
  idle: 'Waiting for item',
  weighing: 'Weighing...',
  scanning: 'Scanning...',
  result: 'Result',
};

const ui = new WebUI();
ui.on_connect(onUIConnected);
ui.on_disconnect(onUIDisconnected);
ui.on_message('state_update', render);

function onUIConnected() {
  errorContainer.style.display = 'none';
  errorContainer.textContent = '';
  ui.send_message('get_initial_state');
}

function onUIDisconnected() {
  errorContainer.style.display = 'block';
  errorContainer.textContent = 'Connection to the board lost. Please check the connection.';
}

function render(state) {
  phaseEl.textContent = PHASE_LABELS[state.phase] || state.phase;
  weightEl.textContent = `${Math.round(state.weight_grams)} g`;

  if (state.phase !== 'result' || !state.result) {
    resultEl.innerHTML = '';
    return;
  }

  const r = state.result;
  if (!r.for_sale) {
    resultEl.innerHTML = `
      <p class="item-name">${r.item_name}</p>
      <p class="reject">Not for sale -- ${r.detail}</p>
    `;
    return;
  }

  resultEl.innerHTML = `
    <p class="item-name">${r.item_name}</p>
    <p class="price-row">
      <span class="strike">$${r.base_price.toFixed(2)}</span>
      <span>${r.discount_pct}% off</span>
    </p>
    <p class="final">$${r.final_price.toFixed(2)}</p>
    ${r.qr_data_uri ? `<img src="${r.qr_data_uri}" alt="Discount QR code">` : ''}
    <p class="code">${r.discount_code || ''}</p>
    <p class="detail">${r.detail}</p>
  `;
}
