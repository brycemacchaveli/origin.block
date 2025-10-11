
import React from 'react';
import Card from '../../components/Card';
import Button from '../../components/Button';
import Input from '../../components/Input';

const AuditReportPage: React.FC = () => {
  return (
    <div className="space-y-6 max-w-2xl mx-auto">
        <div>
            <h1 className="font-sans font-bold text-gray-900 leading-tight text-2xl sm:text-3xl">Audit & Reports</h1>
            <p className="mt-1 font-sans text-base text-gray-600">Generate compliance and audit reports from immutable data.</p>
        </div>
        
        <Card>
            <form className="space-y-6">
                <div>
                    <label htmlFor="reportType" className="block text-sm font-medium text-gray-700 mb-1 uppercase tracking-wide">Report Type</label>
                    <select id="reportType" className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-primary focus:border-brand-primary transition-all duration-200">
                        <option>Loan Audit Trail</option>
                        <option>KYC Compliance Summary</option>
                        <option>AML Transaction Summary</option>
                        <option>Customer Consent History</option>
                    </select>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                    <Input id="startDate" label="Start Date" type="date" />
                    <Input id="endDate" label="End Date" type="date" />
                </div>

                <Input id="entityId" label="Specific Entity ID (Optional)" type="text" placeholder="e.g., LOAN-001" />

                <div className="pt-4 flex justify-end">
                    <Button type="submit" variant="primary">Generate Report</Button>
                </div>
            </form>
        </Card>
    </div>
  );
};

export default AuditReportPage;
