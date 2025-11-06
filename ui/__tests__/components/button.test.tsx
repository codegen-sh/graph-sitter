import { render, screen, fireEvent } from '@testing-library/react';
import { Button } from '@/components/ui/button';

describe('Button Component', () => {
  it('renders button with text', () => {
    render(<Button>Click me</Button>);
    expect(screen.getByText('Click me')).toBeInTheDocument();
  });

  it('handles click events', () => {
    const handleClick = jest.fn();
    render(<Button onClick={handleClick}>Click me</Button>);

    fireEvent.click(screen.getByText('Click me'));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('can be disabled', () => {
    const handleClick = jest.fn();
    render(<Button disabled onClick={handleClick}>Click me</Button>);

    const button = screen.getByText('Click me');
    expect(button).toBeDisabled();

    fireEvent.click(button);
    expect(handleClick).not.toHaveBeenCalled();
  });

  it('shows loading state', () => {
    render(<Button loading>Loading</Button>);

    const button = screen.getByText('Loading');
    expect(button).toBeDisabled();
  });

  it('applies correct variant styles', () => {
    const { rerender } = render(<Button variant="destructive">Delete</Button>);
    let button = screen.getByText('Delete');
    expect(button).toHaveClass('bg-destructive');

    rerender(<Button variant="outline">Cancel</Button>);
    button = screen.getByText('Cancel');
    expect(button).toHaveClass('border');
  });

  it('applies correct size classes', () => {
    const { rerender } = render(<Button size="sm">Small</Button>);
    let button = screen.getByText('Small');
    expect(button).toHaveClass('h-9');

    rerender(<Button size="lg">Large</Button>);
    button = screen.getByText('Large');
    expect(button).toHaveClass('h-11');
  });

  it('is keyboard accessible', () => {
    const handleClick = jest.fn();
    render(<Button onClick={handleClick}>Press me</Button>);

    const button = screen.getByText('Press me');
    button.focus();
    expect(button).toHaveFocus();
  });
});
