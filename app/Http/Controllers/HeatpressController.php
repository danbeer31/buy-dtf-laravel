<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;

class HeatpressController extends Controller
{
    /**
     * Display the heat press instructions page.
     *
     * @return \Illuminate\View\View
     */
    public function index()
    {
        return view('heatpress');
    }
}
