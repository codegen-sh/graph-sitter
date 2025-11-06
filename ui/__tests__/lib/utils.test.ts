import {
  formatDate,
  formatDuration,
  formatFileSize,
  truncate,
  getFileExtension,
  getFileName,
  groupBy,
  sortBy,
  filterBySearch,
  validateCodeSyntax,
} from '@/lib/utils';

describe('Utility Functions', () => {
  describe('formatDuration', () => {
    it('formats milliseconds', () => {
      expect(formatDuration(500)).toBe('500ms');
    });

    it('formats seconds', () => {
      expect(formatDuration(5000)).toBe('5.0s');
    });

    it('formats minutes', () => {
      expect(formatDuration(120000)).toBe('2.0m');
    });

    it('formats hours', () => {
      expect(formatDuration(7200000)).toBe('2.0h');
    });
  });

  describe('formatFileSize', () => {
    it('formats bytes', () => {
      expect(formatFileSize(0)).toBe('0 Bytes');
      expect(formatFileSize(500)).toBe('500 Bytes');
    });

    it('formats kilobytes', () => {
      expect(formatFileSize(1024)).toBe('1 KB');
    });

    it('formats megabytes', () => {
      expect(formatFileSize(1048576)).toBe('1 MB');
    });
  });

  describe('truncate', () => {
    it('truncates long strings', () => {
      expect(truncate('This is a long string', 10)).toBe('This is a ...');
    });

    it('does not truncate short strings', () => {
      expect(truncate('Short', 10)).toBe('Short');
    });
  });

  describe('getFileExtension', () => {
    it('returns file extension', () => {
      expect(getFileExtension('test.py')).toBe('py');
      expect(getFileExtension('component.tsx')).toBe('tsx');
    });

    it('handles files with multiple dots', () => {
      expect(getFileExtension('test.spec.ts')).toBe('ts');
    });

    it('handles files without extension', () => {
      expect(getFileExtension('README')).toBe('');
    });
  });

  describe('getFileName', () => {
    it('extracts file name from path', () => {
      expect(getFileName('/path/to/file.py')).toBe('file.py');
      expect(getFileName('src/components/Button.tsx')).toBe('Button.tsx');
    });
  });

  describe('groupBy', () => {
    it('groups array by key', () => {
      const data = [
        { type: 'a', value: 1 },
        { type: 'b', value: 2 },
        { type: 'a', value: 3 },
      ];

      const grouped = groupBy(data, 'type');
      expect(grouped.a).toHaveLength(2);
      expect(grouped.b).toHaveLength(1);
    });
  });

  describe('sortBy', () => {
    it('sorts array by key ascending', () => {
      const data = [
        { name: 'c', value: 3 },
        { name: 'a', value: 1 },
        { name: 'b', value: 2 },
      ];

      const sorted = sortBy(data, 'name', 'asc');
      expect(sorted[0].name).toBe('a');
      expect(sorted[2].name).toBe('c');
    });

    it('sorts array by key descending', () => {
      const data = [
        { name: 'a', value: 1 },
        { name: 'c', value: 3 },
        { name: 'b', value: 2 },
      ];

      const sorted = sortBy(data, 'name', 'desc');
      expect(sorted[0].name).toBe('c');
      expect(sorted[2].name).toBe('a');
    });
  });

  describe('filterBySearch', () => {
    it('filters array by search query', () => {
      const data = [
        { name: 'Apple', type: 'fruit' },
        { name: 'Banana', type: 'fruit' },
        { name: 'Carrot', type: 'vegetable' },
      ];

      const filtered = filterBySearch(data, 'app', ['name']);
      expect(filtered).toHaveLength(1);
      expect(filtered[0].name).toBe('Apple');
    });

    it('is case insensitive', () => {
      const data = [
        { name: 'Apple' },
        { name: 'BANANA' },
      ];

      const filtered = filterBySearch(data, 'APPLE', ['name']);
      expect(filtered).toHaveLength(1);
    });
  });

  describe('validateCodeSyntax', () => {
    it('validates balanced brackets', () => {
      expect(validateCodeSyntax('function() { return true; }', 'javascript')).toBe(true);
      expect(validateCodeSyntax('def func(): return [1, 2, 3]', 'python')).toBe(true);
    });

    it('detects unbalanced brackets', () => {
      expect(validateCodeSyntax('function() { return true;', 'javascript')).toBe(false);
      expect(validateCodeSyntax('def func(): return [1, 2', 'python')).toBe(false);
    });

    it('rejects empty code', () => {
      expect(validateCodeSyntax('', 'python')).toBe(false);
      expect(validateCodeSyntax('   ', 'python')).toBe(false);
    });
  });
});
