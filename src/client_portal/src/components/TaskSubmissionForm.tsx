import { useState, ChangeEvent, FormEvent } from 'react';
import './TaskSubmissionForm.css';
import { TaskFormData, TaskDomain, TaskComplexity, TaskUrgency, ApiResponse } from '../types';

// Domain base rates (from API - could be fetched dynamically)
const DOMAINS: { value: TaskDomain; label: string; basePrice: number }[] = [
  { value: 'accounting', label: 'Accounting', basePrice: 100 },
  { value: 'legal', label: 'Legal', basePrice: 175 },
  { value: 'data_analysis', label: 'Data Analysis', basePrice: 150 },
];

// Complexity multipliers
const COMPLEXITY: { value: TaskComplexity; label: string; multiplier: number }[] = [
  { value: 'simple', label: 'Simple', multiplier: 1.0 },
  { value: 'medium', label: 'Medium', multiplier: 1.5 },
  { value: 'complex', label: 'Complex', multiplier: 2.0 },
];

// Urgency multipliers
const URGENCY: { value: TaskUrgency; label: string; multiplier: number }[] = [
  { value: 'standard', label: 'Standard (3-5 days)', multiplier: 1.0 },
  { value: 'rush', label: 'Rush (1-2 days)', multiplier: 1.25 },
  { value: 'urgent', label: 'Urgent (same day)', multiplier: 1.5 },
];

// Calculate price using the formula: Base Rate × Complexity × Urgency
const calculatePrice = (
  domain: TaskDomain,
  complexity: TaskComplexity,
  urgency: TaskUrgency
): number | null => {
  const domainData = DOMAINS.find(d => d.value === domain);
  const complexityData = COMPLEXITY.find(c => c.value === complexity);
  const urgencyData = URGENCY.find(u => u.value === urgency);

  if (!domainData || !complexityData || !urgencyData) return null;

  return Math.round(domainData.basePrice * complexityData.multiplier * urgencyData.multiplier);
};

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function TaskSubmissionForm() {
  const [formData, setFormData] = useState<TaskFormData>({
    domain: 'general',
    title: '',
    description: '',
    complexity: 'medium',
    urgency: 'standard',
    clientEmail: '',
    file: null,
  });
  const [estimatedPrice, setEstimatedPrice] = useState<number | null>(null);
  const [discountInfo, setDiscountInfo] = useState<{
    referralDiscount?: number;
    loyaltyDiscount?: number;
    totalDiscount?: number;
  } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [checkoutUrl, setCheckoutUrl] = useState<string | null>(null);

  // Calculate estimated price when form data changes
  const updateEstimatedPrice = (data: TaskFormData) => {
    if (data.domain && data.complexity && data.urgency) {
      const price = calculatePrice(data.domain, data.complexity, data.urgency);
      setEstimatedPrice(price);

      // Apply discounts (example logic)
      const discounts = {
        referralDiscount: 0.1, // 10% referral discount
        loyaltyDiscount: 0.05, // 5% loyalty discount
      };

      if (price) {
        const totalDiscount = price * (discounts.referralDiscount + discounts.loyaltyDiscount);
        setDiscountInfo({
          ...discounts,
          totalDiscount,
        });
      }
    } else {
      setEstimatedPrice(null);
      setDiscountInfo(null);
    }
  };

  const handleChange = (
    e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ) => {
    const { name, value } = e.target;
    const updatedData = { ...formData, [name]: value };
    setFormData(updatedData);
    updateEstimatedPrice(updatedData);
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] || null;
    const updatedData = { ...formData, file };
    setFormData(updatedData);
  };

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSuccess(false);

    try {
      // Prepare form data for submission
      const submitData = new FormData();
      submitData.append('domain', formData.domain);
      submitData.append('title', formData.title);
      submitData.append('description', formData.description);
      submitData.append('complexity', formData.complexity || 'medium');
      submitData.append('urgency', formData.urgency || 'standard');
      submitData.append('client_email', formData.clientEmail);

      if (formData.file) {
        submitData.append('file', formData.file, formData.file.name);
      }

      // Submit to API
      const response = await fetch(`${API_BASE_URL}/api/tasks`, {
        method: 'POST',
        body: submitData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to submit task');
      }

      const result: ApiResponse<{ session_id: string; url: string }> = await response.json();

      if (result.success && result.data) {
        setSuccess(true);
        setCheckoutUrl(result.data.url);
      } else {
        throw new Error(result.error || 'Unexpected response');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  if (success && checkoutUrl) {
    return (
      <div className="success-container">
        <h2>Task Submitted Successfully!</h2>
        <p>Please complete your payment to start processing:</p>
        <a href={checkoutUrl} target="_blank" rel="noopener noreferrer" className="checkout-button">
          Proceed to Payment
        </a>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="task-submission-form">
      <h2>Submit New Task</h2>

      {error && <div className="error-message">{error}</div>}

      <div className="form-group">
        <label htmlFor="domain">Domain</label>
        <select
          id="domain"
          name="domain"
          value={formData.domain}
          onChange={handleChange}
          required
        >
          <option value="">Select a domain</option>
          {DOMAINS.map((d) => (
            <option key={d.value} value={d.value}>
              {d.label}
            </option>
          ))}
        </select>
      </div>

      <div className="form-group">
        <label htmlFor="title">Task Title</label>
        <input
          type="text"
          id="title"
          name="title"
          value={formData.title}
          onChange={handleChange}
          required
          placeholder="e.g., Create financial dashboard"
        />
      </div>

      <div className="form-group">
        <label htmlFor="description">Description</label>
        <textarea
          id="description"
          name="description"
          value={formData.description}
          onChange={handleChange}
          required
          rows={4}
          placeholder="Describe your task requirements..."
        />
      </div>

      <div className="form-row">
        <div className="form-group">
          <label htmlFor="complexity">Complexity</label>
          <select
            id="complexity"
            name="complexity"
            value={formData.complexity}
            onChange={handleChange}
            required
          >
            {COMPLEXITY.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label htmlFor="urgency">Urgency</label>
          <select
            id="urgency"
            name="urgency"
            value={formData.urgency}
            onChange={handleChange}
            required
          >
            {URGENCY.map((u) => (
              <option key={u.value} value={u.value}>
                {u.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="form-group">
        <label htmlFor="clientEmail">Email</label>
        <input
          type="email"
          id="clientEmail"
          name="clientEmail"
          value={formData.clientEmail}
          onChange={handleChange}
          required
          placeholder="your@email.com"
        />
      </div>

      <div className="form-group">
        <label htmlFor="file">Attach File (optional)</label>
        <input
          type="file"
          id="file"
          name="file"
          onChange={handleFileChange}
          accept=".pdf,.doc,.docx,.xls,.xlsx,.csv,.txt"
        />
        <small>Supported formats: PDF, DOC, DOCX, XLS, XLSX, CSV, TXT</small>
      </div>

      {estimatedPrice && (
        <div className="price-estimate">
          <h3>Estimated Price: ${estimatedPrice}</h3>
          {discountInfo && (
            <div className="discount-breakdown">
              {discountInfo.referralDiscount && (
                <p>Referral Discount: -${Math.round(estimatedPrice * discountInfo.referralDiscount)}</p>
              )}
              {discountInfo.loyaltyDiscount && (
                <p>Loyalty Discount: -${Math.round(estimatedPrice * discountInfo.loyaltyDiscount)}</p>
              )}
              {discountInfo.totalDiscount && (
                <p className="total-discount">
                  Total Discount: -${Math.round(discountInfo.totalDiscount)}
                </p>
              )}
            </div>
          )}
        </div>
      )}

      <button type="submit" className="submit-button" disabled={loading}>
        {loading ? 'Submitting...' : 'Submit Task'}
      </button>
    </form>
  );
}

export default TaskSubmissionForm;
