const phaseEl = document.querySelector('#phase');
const weightEl = document.querySelector('#weight');
const hintEl = document.querySelector('#hint');
const resultEl = document.querySelector('#result');
const errorContainer = document.querySelector('#error-container');

const PHASE_LABELS = {
  idle: 'Waiting for item',
  weighing: 'Weighing...',
  scanning: 'Scanning...',
  result: 'Result',
};

const PHASE_HINTS = {
  idle: 'Place an item on the scale',
  weighing: 'Hold still...',
  scanning: 'Reading the item...',
  result: '',
};

const GRADE_LABELS = {
  gradeA: 'Grade A',
  gradeB: 'Grade B',
  gradeC: 'Grade C',
  reject: 'Not fit for sale',
};

const ui = new WebUI();
ui.on_connect(onUIConnected);
ui.on_disconnect(onUIDisconnected);
ui.on_message('state_update', render);

function onUIConnected() {
  errorContainer.hidden = true;
  errorContainer.textContent = '';
  ui.send_message('get_initial_state');
}

function onUIDisconnected() {
  errorContainer.hidden = false;
  errorContainer.textContent = 'Connection to the board lost. Please check the connection.';
}

function euro(amount) {
  return `€${Number(amount).toFixed(2)}`;
}

function itemName(r) {
  return r.item_name || (r.produce_type ? titleCase(r.produce_type) : 'Item');
}

function titleCase(s) {
  return s.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function badgeFor(r) {
  if (r.flow === 'produce' && r.grade) {
    return { cls: `badge badge--${r.grade}`, text: GRADE_LABELS[r.grade] || r.grade };
  }
  return { cls: 'badge badge--packaged', text: 'Packaged' };
}

function basisLine(r) {
  if (r.flow === 'produce') {
    const parts = [];
    if (r.weight_grams != null) parts.push(`${(r.weight_grams / 1000).toFixed(3)} kg`);
    if (r.price_per_kg != null) parts.push(`${euro(r.price_per_kg)}/kg`);
    return parts.join(' · ');
  }
  return null;
}

function render(state) {
  phaseEl.textContent = PHASE_LABELS[state.phase] || state.phase;
  weightEl.textContent = `${Math.round(state.weight_grams || 0)} g`;
  hintEl.textContent = PHASE_HINTS[state.phase] || '';
  hintEl.hidden = !hintEl.textContent;

  if (state.phase !== 'result' || !state.result) {
    resultEl.hidden = true;
    resultEl.innerHTML = '';
    return;
  }

  resultEl.hidden = false;
  resultEl.innerHTML = renderLabel(state.result);
}

function renderLabel(r) {
  const badge = badgeFor(r);
  const basis = basisLine(r);
  const name = itemName(r);

  if (!r.for_sale) {
    return `
      <div class="label label--reject">
        <div class="label__head">
          <p class="label__item">${name}</p>
          <span class="${badge.cls}">${badge.text}</span>
        </div>
        ${basis ? `<p class="label__basis">${basis}</p>` : ''}
        <p class="label__reason">Not for sale</p>
        <p class="label__reason-hint">${r.detail}</p>
      </div>
    `;
  }

  return `
    <div class="label">
      <div class="label__head">
        <p class="label__item">${name}</p>
        <span class="${badge.cls}">${badge.text}</span>
      </div>
      ${basis ? `<p class="label__basis">${basis}</p>` : ''}
      <div class="label__prices">
        ${r.discount_pct ? `<span class="price-was">${euro(r.base_price)}</span>` : ''}
        ${r.discount_pct ? `<span class="price-off">${r.discount_pct}% off</span>` : ''}
        <span class="price-now">${euro(r.final_price)}</span>
      </div>
      ${r.qr_data_uri ? `
        <div class="label__footer">
          <img src="${r.qr_data_uri}" alt="Discount QR code">
          <div>
            <p class="label__code">${r.discount_code || ''}</p>
            <p class="label__code-hint">Scan at checkout to redeem</p>
          </div>
        </div>
      ` : ''}
      <p class="label__detail">${r.detail}</p>
    </div>
  `;
}
