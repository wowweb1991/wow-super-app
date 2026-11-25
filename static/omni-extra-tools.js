(() => {
  'use strict';

  const money = new Intl.NumberFormat('en-PH', { style: 'currency', currency: 'PHP' });
  const number = new Intl.NumberFormat('en-PH', { maximumFractionDigits: 8 });
  const day = 86400000;
  const dateValue = value => Date.parse(value + 'T00:00:00Z');
  const cash = value => money.format(value);
  const percent = value => number.format(value) + '%';
  const lines = value => value.split(/\r?\n/);
  const numeric = (label, min, max) => ({ label, type: 'number', min, max });
  const text = label => ({ label, type: 'textarea' });
  const date = label => ({ label, type: 'date' });
  const clock = label => ({ label, type: 'time' });

  const tools = [
    ['Percentage Calculator', [numeric('Base amount'), numeric('Percentage')],
      (amount, rate) => number.format(amount * rate / 100)],
    ['Percentage Change', [numeric('Starting value', 0.00000001), numeric('Ending value', 0)],
      (start, end) => percent((end - start) / start * 100)],
    ['Markup Calculator', [numeric('Cost in PHP', 0), numeric('Markup %', 0)],
      (cost, rate) => 'Selling price: ' + cash(cost * (1 + rate / 100)) + '\nMarkup: ' + cash(cost * rate / 100)],
    ['Gross Margin Calculator', [numeric('Selling price in PHP', 0.01), numeric('Unit cost in PHP', 0)],
      (price, cost) => 'Gross margin: ' + percent((price - cost) / price * 100) + '\nGross profit: ' + cash(price - cost)],
    ['Bill Splitter', [{ ...numeric('Total in PHP', 0), step: '0.01' }, { ...numeric('Number of people', 1, 100000), step: '1' }],
      (total, people) => {
        const cents = Math.round(total * 100);
        const share = Math.floor(cents / people);
        const extra = cents % people;
        return extra
          ? extra + ' pay ' + cash((share + 1) / 100) + '\n' + (people - extra) + ' pay ' + cash(share / 100)
          : cash(share / 100) + ' each';
      }],
    ['Unit Price Calculator', [numeric('Total price in PHP', 0), numeric('Quantity', 0.00000001)],
      (price, quantity) => 'PHP ' + number.format(price / quantity) + ' per unit'],
    ['Break-even Calculator', [numeric('Fixed costs in PHP', 0), numeric('Selling price per unit in PHP', 0), numeric('Variable cost per unit in PHP', 0)],
      (fixed, price, cost) => {
        if (price <= cost) throw Error('Selling price must exceed variable cost.');
        const exact = fixed / (price - cost);
        const units = Math.ceil(Number(exact.toPrecision(14)));
        return number.format(units) + ' whole units to break even';
      }],
    ['Budget Balance', [numeric('Available budget in PHP', 0), numeric('Total spending in PHP', 0)],
      (budget, spending) => (budget >= spending ? 'Remaining: ' : 'Over budget: ') + cash(Math.abs(budget - spending))],
    ['Temperature Converter', [numeric('Temperature'), { label: 'Input scale', options: ['Celsius', 'Fahrenheit', 'Kelvin'] }],
      (value, scale) => {
        const celsius = scale === 'Celsius' ? value : scale === 'Fahrenheit' ? (value - 32) * 5 / 9 : value - 273.15;
        if (celsius < -273.15 - 1e-10) throw Error('Temperature is below absolute zero.');
        return number.format(celsius) + ' °C\n' + number.format(celsius * 9 / 5 + 32) + ' °F\n' + number.format(celsius + 273.15) + ' K';
      }],
    ['Speed Converter', [numeric('Speed', 0), { label: 'Input unit', options: ['km/h', 'mph', 'm/s'] }],
      (value, unit) => {
        const kmh = value * { 'km/h': 1, mph: 1.609344, 'm/s': 3.6 }[unit];
        return number.format(kmh) + ' km/h\n' + number.format(kmh / 1.609344) + ' mph\n' + number.format(kmh / 3.6) + ' m/s';
      }],
    ['Date Difference', [date('First date'), date('Second date')],
      (first, second) => number.format(Math.abs(dateValue(second) - dateValue(first)) / day) + ' days apart'],
    ['Add Days to Date', [date('Starting date'), { ...numeric('Days to add or subtract', -100000, 100000), step: '1' }],
      (start, days) => new Intl.DateTimeFormat('en-PH', { dateStyle: 'full', timeZone: 'UTC' }).format(dateValue(start) + days * day)],
    ['Time Duration', [clock('Start time'), clock('End time')],
      (start, end) => {
        const minutes = value => Number(value.slice(0, 2)) * 60 + Number(value.slice(3));
        const difference = (minutes(end) - minutes(start) + 1440) % 1440;
        return Math.floor(difference / 60) + ' hours, ' + difference % 60 + ' minutes';
      }],
    ['Text Case Converter', [text('Text'), { label: 'Case', options: ['UPPERCASE', 'lowercase'] }],
      (value, mode) => mode === 'UPPERCASE' ? value.toUpperCase() : value.toLowerCase()],
    ['Line Sorter', [text('One entry per line'), { label: 'Order', options: ['A to Z', 'Z to A'] }],
      (value, order) => {
        const sorted = lines(value.trimEnd()).sort(new Intl.Collator('en-PH', { numeric: true }).compare);
        return (order === 'Z to A' ? sorted.reverse() : sorted).join('\n');
      }],
    ['Duplicate Line Remover', [text('One entry per line')],
      value => [...new Set(lines(value))].join('\n')],
    ['Whitespace Cleaner', [text('Text')],
      value => lines(value).map(line => line.trim().replace(/[^\S\n]+/g, ' ')).join('\n').trim()],
    ['Find and Replace', [text('Text'), { label: 'Find', type: 'text' }, { label: 'Replace with', type: 'text', optional: true }],
      (value, find, replacement) => value.replaceAll(find, () => replacement)],
    ['JSON Formatter', [text('JSON'), { label: 'Format', options: ['Indented', 'Compact'] }],
      (value, format) => {
        try {
          JSON.parse(value);
        } catch {
          throw Error('Enter valid JSON.');
        }
        // Preserve numeric precision, duplicate keys and escapes by formatting tokens directly.
        const tokens = value.match(/"(?:\\[\s\S]|[^"\\])*"|[^\s{}\[\],:]+|[{}\[\],:]/g) || [];
        if (format === 'Compact') return tokens.join('');
        let depth = 0;
        const newline = () => {
          if (depth > 100) throw Error('Use Compact format for JSON nested more than 100 levels.');
          return '\n' + '  '.repeat(depth);
        };
        return tokens.map((token, index) => {
          if (token === '{' || token === '[') {
            if (tokens[index + 1] === (token === '{' ? '}' : ']')) return token;
            depth++;
            return token + newline();
          }
          if (token === '}' || token === ']') {
            if (tokens[index - 1] === (token === '}' ? '{' : '[')) return token;
            depth--;
            return newline() + token;
          }
          if (token === ',') return token + newline();
          return token === ':' ? ': ' : token;
        }).join('');
      }],
    ['URL Component Encoder', [text('Text or encoded component'), { label: 'Action', options: ['Encode', 'Decode'] }],
      (value, action) => {
        try {
          return action === 'Encode' ? encodeURIComponent(value) : decodeURIComponent(value);
        } catch {
          throw Error('Enter a valid URL component.');
        }
      }]
  ];

  const container = document.querySelector('main');
  for (const [title, fields, calculate] of tools) {
    const section = document.createElement('section');
    const heading = document.createElement('h2');
    const form = document.createElement('form');
    const output = document.createElement('output');
    const submit = document.createElement('button');
    heading.textContent = title;
    submit.textContent = 'Run';
    output.setAttribute('aria-live', 'polite');

    const inputs = fields.map(field => {
      const label = document.createElement('label');
      const input = document.createElement(field.options ? 'select' : field.type === 'textarea' ? 'textarea' : 'input');
      if (field.options) {
        for (const option of field.options) input.add(new Option(option, option));
      } else if (field.type === 'textarea') {
        input.rows = 4;
        input.maxLength = 50000;
      } else {
        input.type = field.type;
        if (field.min !== undefined) input.min = field.min;
        if (field.max !== undefined) input.max = field.max;
        if (field.type === 'number') input.step = field.step ?? 'any';
      }
      input.required = !field.optional;
      label.append(field.label, input);
      form.append(label);
      return input;
    });

    form.addEventListener('submit', event => {
      event.preventDefault();
      try {
        const values = inputs.map(input => input.type === 'number' ? input.valueAsNumber : input.value);
        if (values.some(value => typeof value === 'number' && (!Number.isFinite(value) || Math.abs(value) > 1e12))) {
          throw Error('Enter numbers between −1 trillion and 1 trillion.');
        }
        output.textContent = calculate(...values);
      } catch (error) {
        output.textContent = error.message;
      }
    });

    form.append(submit, output);
    section.append(heading, form);
    container.append(section);
  }
})();
