import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import Card from '../../components/Card';
import Button from '../../components/Button';
import Badge from '../../components/Badge';
import { mockLoans } from '../../services/mockData';
import { ChevronDownIcon } from '../../components/icons';

const Accordion: React.FC<{ title: string; children: React.ReactNode; defaultOpen?: boolean }> = ({ title, children, defaultOpen = false }) => {
    const [isOpen, setIsOpen] = useState(defaultOpen);

    return (
        <div className="border-b border-gray-200 last:border-b-0">
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="w-full flex justify-between items-center py-4 text-left"
            >
                <h3 className="font-sans font-semibold text-gray-800 text-lg">{title}</h3>
                <ChevronDownIcon className={`w-5 h-5 text-gray-600 transform transition-transform ${isOpen ? 'rotate-180' : ''}`} />
            </button>
            {isOpen && <div className="pb-4 text-gray-700">{children}</div>}
        </div>
    );
};

const LoanDetailsPage: React.FC = () => {
    const { id } = useParams();
    const loan = mockLoans.find(l => l.id === id);

    if (!loan) {
        return <p>Loan not found.</p>;
    }

    return (
        <div className="space-y-6">
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                <div>
                    <h1 className="font-sans font-bold text-gray-900 leading-tight text-2xl sm:text-3xl">Loan Details</h1>
                    <div className="flex items-center space-x-2 mt-1">
                        <span className="font-mono text-sm text-gray-600">{loan.id}</span>
                        <Badge status={loan.status} />
                    </div>
                </div>
                <div className="flex space-x-2">
                    <Button variant="secondary">Update Status</Button>
                    <Button variant="primary">Approve</Button>
                </div>
            </div>

            <Card>
                <Accordion title="Applicant Details" defaultOpen>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div><strong className="block text-gray-500 text-sm">Name:</strong> {loan.applicantName}</div>
                        <div><strong className="block text-gray-500 text-sm">Loan Type:</strong> {loan.loanType}</div>
                        <div><strong className="block text-gray-500 text-sm">Amount:</strong> ${loan.amount.toLocaleString()}</div>
                        <div><strong className="block text-gray-500 text-sm">Submitted:</strong> {loan.submittedDate}</div>
                    </div>
                </Accordion>
                <Accordion title="Documents">
                     <ul className="space-y-2">
                        {loan.documents.map(doc => (
                           <li key={doc.id} className="flex justify-between items-center p-2 bg-gray-50 rounded-md">
                               <div>
                                   <p className="font-medium text-gray-800">{doc.name}</p>
                                   <p className="font-mono text-xs text-gray-500">{doc.hash}</p>
                               </div>
                               <Button variant="link">Verify</Button>
                           </li>
                        ))}
                     </ul>
                </Accordion>
                <Accordion title="Immutable History">
                     <div className="space-y-4">
                        {loan.history.map(event => (
                           <div key={event.id} className="flex items-start space-x-3 py-3 border-b border-gray-100 last:border-b-0">
                                <div className="text-right">
                                    <p className="font-mono text-xs text-gray-500 whitespace-nowrap">{event.timestamp.split(' ')[0]}</p>
                                    <p className="font-mono text-xs text-gray-400 whitespace-nowrap">{event.timestamp.split(' ')[1]}</p>
                                </div>
                                <div className="flex-shrink-0 w-3 h-3 bg-gray-300 rounded-full mt-1.5"></div>
                                <div>
                                    <p className="font-medium text-gray-800">{event.action} by {event.actor}</p>
                                    <p className="text-sm text-gray-600">{event.details}</p>
                                </div>
                           </div>
                        ))}
                    </div>
                </Accordion>
            </Card>
        </div>
    );
};

export default LoanDetailsPage;