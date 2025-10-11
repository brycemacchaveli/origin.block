
import React from 'react';
import Card from '../../components/Card';
import Button from '../../components/Button';
import Input from '../../components/Input';

const NewLoanPage: React.FC = () => {
  return (
    <div className="space-y-6 max-w-2xl mx-auto">
        <div>
            <h1 className="font-sans font-bold text-gray-900 leading-tight text-2xl sm:text-3xl">New Loan Application</h1>
            <p className="mt-1 font-sans text-base text-gray-600">Enter the details for the new loan.</p>
        </div>
        
        <Card>
            <form className="space-y-6">
                <Input id="applicantName" label="Applicant Full Name" type="text" placeholder="e.g., John Doe" />
                <Input id="loanAmount" label="Loan Amount" type="number" placeholder="e.g., 50000" />
                
                <div>
                    <label htmlFor="loanType" className="block text-sm font-medium text-gray-700 mb-1 uppercase tracking-wide">Loan Type</label>
                    <select id="loanType" className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-primary focus:border-brand-primary transition-all duration-200">
                        <option>Mortgage</option>
                        <option>Personal Loan</option>
                        <option>Auto Loan</option>
                    </select>
                </div>
                
                <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1 uppercase tracking-wide">Documents</label>
                    <div className="mt-1 flex justify-center px-6 pt-5 pb-6 border-2 border-gray-300 border-dashed rounded-md">
                        <div className="space-y-1 text-center">
                            <svg className="mx-auto h-12 w-12 text-gray-400" stroke="currentColor" fill="none" viewBox="0 0 48 48" aria-hidden="true">
                                <path d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                            <div className="flex text-sm text-gray-600">
                                <label htmlFor="file-upload" className="relative cursor-pointer bg-white rounded-md font-medium text-brand-primary hover:text-brand-primary focus-within:outline-none focus-within:ring-2 focus-within:ring-offset-2 focus-within:ring-brand-primary">
                                    <span>Upload a file</span>
                                    <input id="file-upload" name="file-upload" type="file" className="sr-only" />
                                </label>
                                <p className="pl-1">or drag and drop</p>
                            </div>
                            <p className="text-xs text-gray-500">PNG, JPG, PDF up to 10MB</p>
                        </div>
                    </div>
                </div>

                <div className="pt-4 flex justify-end">
                    <Button type="submit" variant="primary">Submit Application</Button>
                </div>
            </form>
        </Card>
    </div>
  );
};

export default NewLoanPage;
