// @vitest-environment jsdom
import {
  act,
  cleanup,
  render,
  renderHook,
  screen,
} from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, RateLimited } from '../api/errors';
import { CooldownNotice } from '../components/CooldownNotice';
import i18n from '../i18n';
import { formatWait, useCooldown } from './useCooldown';

describe('formatWait', () => {
  it('shows minutes and seconds, and hours past an hour', () => {
    expect(formatWait(5)).toBe('0:05');
    expect(formatWait(900)).toBe('15:00');
    expect(formatWait(3723)).toBe('1:02:03');
  });
});

describe('useCooldown', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => {
    vi.useRealTimers();
    cleanup();
  });

  it('starts from Retry-After and counts down to zero', () => {
    const { result } = renderHook(() => useCooldown());

    let handled = false;
    act(() => {
      handled = result.current.trigger(new RateLimited(3));
    });
    expect(handled).toBe(true);
    expect(result.current.secondsLeft).toBe(3);
    expect(result.current.active).toBe(true);

    act(() => vi.advanceTimersByTime(1000));
    expect(result.current.secondsLeft).toBe(2);

    act(() => vi.advanceTimersByTime(2000));
    expect(result.current.secondsLeft).toBe(0);
    expect(result.current.active).toBe(false);
  });

  it('falls back to a minute when the 429 had no Retry-After', () => {
    const { result } = renderHook(() => useCooldown());
    act(() => {
      result.current.trigger(new RateLimited(null));
    });
    expect(result.current.secondsLeft).toBe(60);
  });

  it('leaves other errors to the caller', () => {
    const { result } = renderHook(() => useCooldown());
    let handled = true;
    act(() => {
      handled = result.current.trigger(new ApiError('nope', 500));
    });
    expect(handled).toBe(false);
    expect(result.current.active).toBe(false);
  });
});

describe('CooldownNotice', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('en');
  });
  afterEach(cleanup);

  it('shows the remaining wait and announces only the static part', () => {
    render(<CooldownNotice seconds={125} />);
    expect(screen.getByRole('alert').textContent).toBe('Too many attempts.');
    expect(screen.getByRole('timer').textContent).toBe('Try again in 2:05.');
  });

  it('follows the interface language', async () => {
    await i18n.changeLanguage('ro');
    render(<CooldownNotice seconds={125} />);
    expect(screen.getByRole('alert').textContent).toBe('Prea multe încercări.');
    expect(screen.getByRole('timer').textContent).toBe(
      'Încercați din nou peste 2:05.'
    );
  });

  it('renders nothing once the wait is over', () => {
    const { container } = render(<CooldownNotice seconds={0} />);
    expect(container.innerHTML).toBe('');
  });
});
