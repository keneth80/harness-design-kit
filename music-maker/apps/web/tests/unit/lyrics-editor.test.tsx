import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import * as React from 'react';
import { LyricsEditor } from '@/components/studio/lyrics-editor';

function Harness() {
  const [v, setV] = React.useState('');
  return <LyricsEditor value={v} onChange={setV} />;
}

describe('LyricsEditor', () => {
  it('renders empty state with 0 lines and 0 syllables', () => {
    render(<Harness />);
    expect(screen.getByTestId('line-count')).toHaveTextContent('0');
    expect(screen.getByTestId('syllable-count')).toHaveTextContent('0');
  });

  it('updates line count when user types lyrics', async () => {
    const user = userEvent.setup();
    render(<Harness />);
    const textarea = screen.getByTestId('lyrics-textarea');
    await user.type(textarea, '한 줄{enter}두 번째 줄');
    expect(screen.getByTestId('line-count')).toHaveTextContent('2');
  });

  it('inserts [Verse] structure tag on click', async () => {
    const user = userEvent.setup();
    render(<Harness />);
    await user.click(screen.getByTestId('insert-verse'));
    const textarea = screen.getByTestId(
      'lyrics-textarea',
    ) as HTMLTextAreaElement;
    expect(textarea.value).toContain('[Verse]');
  });
});
