import defaultTheme from 'tailwindcss/defaultTheme';
import forms from '@tailwindcss/forms';

/** @type {import('tailwindcss').Config} */
export default {
    content: [
        './vendor/laravel/framework/src/Illuminate/Pagination/resources/views/*.blade.php',
        './storage/framework/views/*.php',
        './resources/views/**/*.blade.php',
    ],

    theme: {
        extend: {
            fontFamily: {
                sans: ['Figtree', ...defaultTheme.fontFamily.sans],
                blinker: ['Blinker', 'sans-serif'],
                ubuntu: ['Ubuntu', 'sans-serif'],
            },
            colors: {
                'sp-primary': '#000000', // Adjust based on FuelPHP if known, assuming black
                'sp-secondary': '#6c757d', // Adjust based on FuelPHP if known, assuming gray
            }
        },
    },

    plugins: [forms],
};
