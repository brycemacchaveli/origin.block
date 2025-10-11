import React from 'react';

type ButtonProps = {
  children: React.ReactNode;
  // FIX: The onClick handler should accept a React.MouseEvent to allow for event handling like stopPropagation.
  onClick?: (event: React.MouseEvent<HTMLButtonElement>) => void;
  type?: 'button' | 'submit' | 'reset';
  variant?: 'primary' | 'secondary' | 'destructive' | 'link';
  className?: string;
  disabled?: boolean;
};

const Button: React.FC<ButtonProps> = ({
  children,
  onClick,
  type = 'button',
  variant = 'primary',
  className = '',
  disabled = false,
}) => {
  const baseClasses = 'font-semibold py-3 px-6 rounded-lg focus:outline-none focus:ring-2 focus:ring-opacity-75 transition-all duration-200 inline-flex items-center justify-center';
  
  const variantClasses = {
    primary: 'bg-brand-primary text-white shadow-md hover:bg-opacity-90 focus:ring-brand-primary',
    secondary: 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-50 focus:ring-gray-200',
    destructive: 'bg-brand-error text-white shadow-md hover:bg-opacity-90 focus:ring-brand-error',
    link: 'text-brand-primary hover:underline font-medium p-0',
  };

  const disabledClasses = 'opacity-50 cursor-not-allowed';

  return (
    <button
      type={type}
      onClick={onClick}
      className={`${baseClasses} ${variantClasses[variant]} ${disabled ? disabledClasses : ''} ${className}`}
      disabled={disabled}
    >
      {children}
    </button>
  );
};

export default Button;