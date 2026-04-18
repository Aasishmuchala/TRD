import { useState } from 'react'

const FIELDS = [
  { key: 'nifty_spot', label: 'NIFTY Spot', placeholder: '22500', step: 50, min: 5000, max: 50000 },
  { key: 'india_vix', label: 'India VIX', placeholder: '14.5', step: 0.1, min: 5, max: 80 },
  { key: 'fii_flow_5d', label: 'FII Flow 5D (₹Cr)', placeholder: '-1200', step: 100, min: -50000, max: 50000 },
  { key: 'dii_flow_5d', label: 'DII Flow 5D (₹Cr)', placeholder: '800', step: 100, min: -50000, max: 50000 },
  { key: 'usd_inr', label: 'USD/INR', placeholder: '83.2', step: 0.1, min: 60, max: 100 },
  { key: 'dxy', label: 'DXY Index', placeholder: '104.5', step: 0.1, min: 80, max: 130 },
  { key: 'pcr_index', label: 'PCR (Index)', placeholder: '1.1', step: 0.05, min: 0.2, max: 3.0 },
  { key: 'max_pain', label: 'Max Pain', placeholder: '22400', step: 50, min: 5000, max: 50000 },
  { key: 'dte', label: 'Days to Expiry', placeholder: '5', step: 1, min: 0, max: 60, isInt: true },
]

const CONTEXTS = ['normal', 'pre_budget', 'post_budget', 'rbi_policy', 'election', 'global_crisis', 'earnings_season', 'expiry_week']

const DEFAULT_VALUES = {
  nifty_spot: '',
  india_vix: '',
  fii_flow_5d: '',
  dii_flow_5d: '',
  usd_inr: '',
  dxy: '',
  pcr_index: '',
  max_pain: '',
  dte: '',
  context: 'normal',
}

export default function CustomScenarioForm({ onSimulate, isLoading, onClose }) {
  const [values, setValues] = useState(DEFAULT_VALUES)
  const [errors, setErrors] = useState({})

  const handleChange = (key, val) => {
    setValues((prev) => ({ ...prev, [key]: val }))
    if (errors[key]) setErrors((prev) => ({ ...prev, [key]: null }))
  }

  const validate = () => {
    const errs = {}
    if (!values.nifty_spot) errs.nifty_spot = 'Required'
    const nifty = parseFloat(values.nifty_spot)
    if (values.nifty_spot && (isNaN(nifty) || nifty < 5000)) errs.nifty_spot = 'Invalid'

    for (const f of FIELDS) {
      if (values[f.key] !== '' && values[f.key] !== undefined) {
        const num = f.isInt ? parseInt(values[f.key]) : parseFloat(values[f.key])
        if (isNaN(num)) errs[f.key] = 'Invalid number'
      }
    }

    setErrors(errs)
    return Object.keys(errs).length === 0
  }

  const handleSubmit = () => {
    if (!validate()) return

    const data = { context: values.context }
    for (const f of FIELDS) {
      if (values[f.key] !== '' && values[f.key] !== undefined) {
        data[f.key] = f.isInt ? parseInt(values[f.key]) : parseFloat(values[f.key])
      }
    }

    // Fill defaults for required fields that weren't provided
    if (!data.india_vix) data.india_vix = 15.0
    if (!data.fii_flow_5d) data.fii_flow_5d = 0
    if (!data.dii_flow_5d) data.dii_flow_5d = 0
    if (!data.usd_inr) data.usd_inr = 83.0
    if (!data.dxy) data.dxy = 104.0
    if (!data.pcr_index) data.pcr_index = 1.0
    if (!data.max_pain) data.max_pain = data.nifty_spot
    if (!data.dte && data.dte !== 0) data.dte = 5

    onSimulate({
      ...data,
      name: 'Custom Scenario',
      description: `NIFTY ${data.nifty_spot} | VIX ${data.india_vix} | ${values.context}`,
    })
  }

  const handleReset = () => {
    setValues(DEFAULT_VALUES)
    setErrors({})
  }

  return (
    <div className="terminal-card-lg p-5 flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <div className="section-header mb-0">Custom Scenario</div>
        {onClose && (
          <button
            onClick={onClose}
            aria-label="Close custom scenario form"
            className="text-onSurfaceDim hover:text-onSurface transition-colors"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-4 h-4" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>

      <div className="grid grid-cols-3 gap-3 mb-4">
        {FIELDS.map((f) => (
          <div key={f.key}>
            <label htmlFor={f.key} className="text-[10px] font-mono text-onSurfaceDim uppercase block mb-1">
              {f.label}
              {f.key === 'nifty_spot' && <span className="text-bear ml-0.5">*</span>}
            </label>
            <input
              id={f.key}
              type="number"
              step={f.step}
              min={f.min}
              max={f.max}
              placeholder={f.placeholder}
              value={values[f.key]}
              onChange={(e) => handleChange(f.key, e.target.value)}
              aria-invalid={errors[f.key] ? 'true' : 'false'}
              aria-describedby={errors[f.key] ? `${f.key}-error` : undefined}
              className={`w-full bg-surface-1 border rounded-md px-2.5 py-1.5 text-xs font-mono text-onSurface placeholder:text-onSurfaceDim/40 outline-none focus:border-primary/40 transition-colors ${
                errors[f.key] ? 'border-bear/40' : 'border-gray-200'
              }`}
            />
            {errors[f.key] && (
              <span id={`${f.key}-error`} className="text-[9px] font-mono text-bear mt-0.5 block" role="alert">{errors[f.key]}</span>
            )}
          </div>
        ))}
      </div>

      {/* Context selector */}
      <fieldset className="mb-4">
        <legend className="text-[10px] font-mono text-onSurfaceDim uppercase block mb-1.5">
          Market Context
        </legend>
        <div className="flex flex-wrap gap-1.5">
          {CONTEXTS.map((ctx) => (
            <button
              key={ctx}
              onClick={() => handleChange('context', ctx)}
              aria-pressed={values.context === ctx}
              className={`px-2.5 py-1 rounded-md text-[10px] font-mono transition-all border ${
                values.context === ctx
                  ? 'bg-primary/10 text-primary border-primary/20'
                  : 'bg-surface-1 text-onSurfaceDim border-gray-200 hover:border-gray-300'
              }`}
            >
              {ctx.replace(/_/g, ' ')}
            </button>
          ))}
        </div>
      </fieldset>

      {/* Actions */}
      <div className="flex items-center gap-3">
        <button
          onClick={handleSubmit}
          disabled={isLoading || !values.nifty_spot}
          aria-label={isLoading ? 'Simulation in progress' : 'Run custom scenario simulation'}
          className="flex-1 btn-primary disabled:opacity-30 disabled:cursor-not-allowed flex items-center justify-center gap-2 h-10"
        >
          {isLoading ? (
            <span className="flex items-center gap-2">
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" aria-hidden="true">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"/>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
              </svg>
              <span className="font-mono text-xs">SIMULATING...</span>
            </span>
          ) : (
            <span className="font-mono text-xs tracking-wider">RUN CUSTOM</span>
          )}
        </button>
        <button
          onClick={handleReset}
          aria-label="Reset all form fields to defaults"
          className="px-4 h-10 rounded-lg text-[10px] font-mono text-onSurfaceDim border border-gray-200 hover:bg-surface-1 transition-colors"
        >
          RESET
        </button>
      </div>
    </div>
  )
}
