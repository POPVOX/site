// Auto-size textareas as the user enters input.
jQuery.fn.input_autosize = function() {
  var resizer = function(elem, c) {
	var val = jQuery(elem).val();
	if (elem.nodeName.toUpperCase() == "TEXTAREA") {
		var numlines = 1;
		var nchars = 0;
		for (var i = 0; i < val.length; i++) {
			if (val.charAt(i) == '\n') { numlines++; nchars = 0; }
			if (nchars++ == 80) { numlines++; nchars = 0; } // approximate wrap?
		}
		if (c == 13) numlines++;
		if (numlines < 3) numlines = 3; // minimum size for a textarea that looks ok
		jQuery(elem).attr('rows', numlines);
	}
  }
  return this.each(function(){
	jQuery(this).keydown(function(c) { resizer(this, c.which); });
	jQuery(this).bind('paste', function(e) { resizer(this, 0); }); // IE only?
	jQuery(this).bind('cut', function(e) { resizer(this, 0); }); // IE only?
	jQuery(this).blur(function() { resizer(this, 0); }); // in case we missed a cut/paste
	resizer(this, 0); // resize it immediately
  });
};

// Display a default value in text fields with a "default" class until
// user focuses the field, at which point the field is cleared and
// the "default" class is removed. If the user leaves the field and
// it's empty, the default text is replaced.
//
// If value is null then it works differently: the existing text in the
// field is taken to be its existing/default value. The "default" class
// is applied. When the field takes focus, the text is left unchanged
// so the user can edit the existing value but the default class is
// removed. When the user leaves the field, if it has the same value
// as its original value the default class is put back. So, the user
// can see if he has made a change.
jQuery.fn.input_default = function(value) {
  return this.each(function(){
	var default_value = value;
	var clear_on_focus = true;
	if (!default_value) {
		// If no value is specified, the default is whatever is currently
		// set in field but we don't do a clear-on-focus.
		default_value = jQuery(this).val();
		jQuery(this).addClass("default");
		clear_on_focus = false;
	} else if (jQuery(this).val() == "") {
		// Otherwise, if the field is empty, replace it with the default.
		jQuery(this).val(default_value);
		jQuery(this).addClass("default");
	}
	jQuery(this).focus(function() {
		if (jQuery(this).val() == default_value && clear_on_focus)
			jQuery(this).val("");
		jQuery(this).removeClass("default");
	});
	jQuery(this).blur(function() {
		if (clear_on_focus) {
			if (jQuery(this).val() == "") {
				jQuery(this).val(default_value);
				jQuery(this).addClass("default");
			}
		} else {
			if (jQuery(this).val() == default_value) {
				jQuery(this).addClass("default");
			}
		}
	});
  });
};

function clear_default_fields(form) {
	for (var i = 0; i < form.elements.length; i++) {
		if ($(form.elements[i]).hasClass('default'))
			$(form.elements[i]).val('');
	}
}

// This provides a delayed keyup event that fires once
// even if there are multiple keyup events between the
// first and the time the event handler is called.
jQuery.fn.keyup_delayed = function(callback, delay) {
  if (!delay) delay = 450;
  return this.each(function(){
	var last_press = null;
	var n = jQuery(this);
	n.textchange(function() {
		last_press = (new Date()).getTime();
		n.delay(delay);
		n.queue(function(next) { if (last_press != null && ((new Date()).getTime() - last_press > delay*.75)) { callback.call(n[0]); last_press = null; } next(); } );
			// callback is called with .call(n[0]) to set 'this' back to the original this, rather than the window
			// element, which seems to be what is set on any delayed callback?
	});
  });
}

jQuery.fn.keydown_enter = function(callback) {
  return this.each(function(){
	jQuery(this).keydown(function(ev) {
		if (ev.keyCode == '13')
			callback()
	});
  });
}

jQuery.fn.textchange = function(callback) {
  return this.each(function(){
    var n = jQuery(this);
	n.keyup(callback);
	n.change(callback);
	n.bind("paste", callback);
	n.bind("cut", callback);
	n.bind("onpropertychange", callback);
	n.attr('AutoComplete', 'off'); // because it won't trigger this event
  });
}

jQuery.fn.set_text = function(text) {
  return this.each(function(){
	jQuery(this).val(text);
	jQuery(this).removeClass("default");
	jQuery(this).keyup();
  });
}

jQuery.fn.inline_edit = function(callback, createeditor) {
	return this.each(function(){
		var inline = jQuery(this);
		
		if (createeditor) {
			$('<div id="' + this.getAttribute("id") + '_editor" style="display: none">'
				+ ((createeditor == 'textarea' || createeditor == 'tinymce')
					? '<textarea '
					: '<input type="text" ' )
				+ 'id="' + this.getAttribute("id") + '_textarea"/>'
				+ '</div>').insertAfter(inline);
				
			var textarea = $("#" + this.getAttribute("id") + "_textarea");
			textarea.css('font-size', "inherit");
				
			if (createeditor == "input") {
				textarea.css('width', "100%");
				textarea.val(inline.text());
			} else if (createeditor == "textarea") {
				textarea.css('width', inline.css('width'));
				textarea.input_autosize();
				// textareas are normally used when there is some external HTMLizing going on
			} else if (createeditor == "tinymce") {
				textarea.css('width', inline.css('width'));
				tinyMCE.execCommand("mceAddControl", true, this.getAttribute("id") + "_textarea");
			}
		}
		
		var editor = $("#" + this.getAttribute("id") + "_editor");
		var textarea = $("#" + this.getAttribute("id") + "_textarea");
		var editbtn = $("#" + this.getAttribute("id") + "_editbtn");

		var blurfunc = function() {
			if (createeditor == "textarea")
				inline.height(textarea.height());
			editor.hide();
			inline.fadeIn();
			inline.removeClass("inlineedit_active");
			editbtn.fadeIn();
			
			if (createeditor == "input")
				inline.text(textarea.val());
			else if (createeditor == "tinymce")
				inline.html(textarea.val());
			
			if (callback)
				callback(textarea.val(), inline,
					function() {
						inline.height('auto');
					});
		};
		
		inline.addClass("inlineedit");
		inline.click(function() {
			if (inline.hasClass("inlineedit_active"))
				return;
			inline.addClass("inlineedit_active");
			inline.hide();
			editor.show();
			textarea.focus();
			editbtn.fadeOut();
			if (createeditor == "input") {
				textarea.val(inline.text());
			} else if (createeditor == "textarea") {
				// textareas are normally used when there is some external HTMLizing going on
			} else if (createeditor == "tinymce") {
				var mce = tinyMCE.getInstanceById(this.getAttribute("id") + "_textarea");
				mce.setContent(inline.html());
				mce.on_save = function() { blurfunc(); }
			}
		});
		
		if (createeditor != "tinymce")
			textarea.blur(blurfunc);
		if (createeditor == "input")
			textarea.keydown_enter(blurfunc);
	});
};

function enableWhenFormHasData(submitid, fields) {
	updater = function() {
		var hasdata = false;
		for (f in fields)
			if (!$(f).hasClass('default'))
				hasdata = true;
		$(submitid).attr('disabled', hasdata ? '' : '1');
	}
	for (f in fields)
		$(f).keyup(updater);
	updater();
}

function ajaxform(url, postdata, fields, actions) {
	// create copies of postdata and fields so we can modify them
	
	var c = { };
	for (var property in postdata)
		c[property] = postdata[property];
	
	var d = { };
	for (var property in actions)
		d[property] = actions[property];
	
	// add into postdata the resolved value of each field
	//    if fields have a class of default, then null out the value
	//    for checkbox fields, pass 0 or 1.
	
	for (var field in fields) {
		if (fields[field] == "") {
			// ignore
		} else if (typeof fields[field] == "function") {
			v = fields[field]();
			if (v == null) continue;
		} else {
			var n = jQuery(fields[field]);
			var v = n.val()
			if (n.hasClass("default")) continue;
			if (!n[0]) alert("Bad field name " + field);
			if (n[0].nodeName.toLowerCase() == "input" && n[0].getAttribute('type') && n[0].getAttribute('type').toLowerCase() == "checkbox") {
				if (n[0].checked)
					v = "1";
				else
					v = "0";
			}
		}
		c[field] = v;
	}
	
	ajax(url, c, d);
}

function ajax(url, postdata, actions) {
	if (actions == null) actions = {};
	
	// Disable the button while we're processing.
	if (actions.savebutton) {
		if ($('#' + actions.savebutton).attr('disabled')) return;
		$('#' + actions.savebutton).attr('disabled', '1');
	}
	
	// Let the user know we're starting in #statusfield with #statusstart if provided.
	// Normally this shouldn't be used because ajax calls should be fast enough that
	// there is no need to flash a message the user won't have time to read, especially
	// if it's in red and might scare the user.
	if (actions.statusfield && actions.statusstart) {
		$('#' + actions.statusfield).text(actions.statusstart);
		$('#' + actions.statusfield).fadeIn();
	}
	
	$.ajax({ 
		type: (!actions.method ? "POST" : actions.method),
		url: url,
		data: postdata,
		complete:
			function(res, status) {
				// If we have any per-field status spans, then hide them since we may have
				// put error messages in them from the last round.
				if (postdata && actions.statusfield)
					for (var f in postdata)
						$('#' + actions.statusfield + "_" + f).hide();
				
				// Reset the button so user can try again. Do this before any callbacks
				// in case the callback changes the state.
				if (actions.savebutton)
					$('#' + actions.savebutton).attr('disabled', '');
				if (status != "success" || res.responseText == "")
					res = { status: "generic-failure" };
				else
					res = eval('(' + res.responseText + ')');
				if (res && res.status == "success") {
					if (actions.statusfield) { // display message from server if given
						if (res && res.status != "generic-failure" && res.msg && res.msg != "") {
							$('#' + actions.statusfield).text(res.msg);
							$('#' + actions.statusfield).fadeIn();
						} else if (actions.statussuccess) { // clear status
							$('#' + actions.statusfield).text(actions.statussuccess);
							$('#' + actions.statusfield).fadeIn();
							$('#' + actions.statusfield).delay(1000).fadeOut();
						} else { // clear status
							$('#' + actions.statusfield).text("Finished.");
							$('#' + actions.statusfield).hide(); // don't fade out in case callback wants to show it again --- fade out will keep going
						}
					}
					if (actions.success) // user callback
						actions.success(res);
				} else {
					if (actions.statusfield) {
						if (res && res.byfield) {
							// An error message is given on a field by field basis. The form
							// must have corresponding field #statusfield_field spans for errors.
							for (var field in res.byfield) {
								var f2 = "#" + actions.statusfield + '_' + field;
								$(f2).fadeIn();
								$(f2).text(res.byfield[field]);
							}
							$('#' + actions.statusfield).fadeIn();
							//$('#' + actions.statusfield).text("There were errors. Please see above.");
						} else if (res && res.status != "generic-failure" && res.msg && res.msg != "") {
							// If a message was specified, display it. If the message is tied
							// to a field and we have a span for #statusfield_fieldname
							// then put the error message there and display a generic
							// error in the main status field.
							var f2 = actions.statusfield + '_' + (res.field ? res.field : "");
							if (document.getElementById(f2)) { 
								$('#' + actions.statusfield).fadeIn();
								$('#' + actions.statusfield).text("There were errors. Please see above.");
								$('#' + f2).fadeIn();
								$('#' + f2).text(res.msg);
							} else {
								$('#' + actions.statusfield).fadeIn();
								$('#' + actions.statusfield).text(res.msg);
							}
						} else if (actions.statusfail) {
							// No message was provided so use our own message.
							$('#' + actions.statusfield).fadeIn();
							$('#' + actions.statusfield).text(actions.statusfail);
						} else {
							// No message was provided and the caller didn't give a
							// failure message, so display a generic message.
							$('#' + actions.statusfield).fadeIn();
							$('#' + actions.statusfield).text("Could not take action at this time.");
						}
					}
					
					if (actions.failure) // user callback
						actions.failure(res);
				}
			}
	});
}

// Turn a <ul class="tabs"><li><a href="#tabname"><span>Tab Item</span></a></li></ul>
// list into tabs that are fragment-aware. Unless the tab panes are hidden statically, this should
// be called after all of the panes are loaded in the DOM so that all but the first pane can be hidden.
jQuery.fn.pvtabs = function(tab_change_callback) {
	return this.each(function(){
		var ul = $(this);
			
		var open_tab = function (is_initial) {
			// get the tab specified in the window location hash. However, support tabname=info
			// tab "arguments".
			var hash_tab = window.location.hash;
			var hash_argument = null;
			if (hash_tab.indexOf("=") > 0) {
				hash_argument = hash_tab.substr(hash_tab.indexOf("=")+1);
				hash_tab = hash_tab.substr(0, hash_tab.indexOf("="));
			}
			
			// find the matching tab from the window location hash
			var active_tab;
			ul.find('li a').each(function() {
				var tabname = this.getAttribute("href").substr(this.getAttribute("href").indexOf("#")+1);
				if ("#" + tabname == hash_tab)
					active_tab = tabname;
			});
			
			// if the hash doesn't correspond with a tab name, and this isn't on page
			// load, then just abort.
			if (!active_tab && !is_initial) return;
			
			// if this is executing on page load and the window hash didn't match a tab,
			// open the first tab by default.
			if (!active_tab) {
				ul.find('li a').each(function() {
					var tabname = this.getAttribute("href").substr(this.getAttribute("href").indexOf("#")+1);
					if (!active_tab)
						active_tab = tabname;
				});
			}
				
			// if there are no tabs, abort
			if (!active_tab) return;
			
			if (!is_initial) {
				// if the user is scrolled far down on the page, scroll the user back up
				var tabs_top = ul.offset().top;
				if ($(window).scrollTop() > tabs_top + 50)
					//$(window).scrollTop(tabs_top);
					$('html,body').animate({scrollTop: tabs_top}); // works across browsers?
			}
			
			// find the matching tab and make it active
			// since tabs can share tab_panes, do hide before show
			var tabs_to_hide = "";
			var tabs_to_show = "";
			ul.find('li').removeClass("active");
			ul.find('li a').each(function() {
				var tabname = this.getAttribute("href").substr(this.getAttribute("href").indexOf("#")+1);
				if (tabname == active_tab) {
					$(this.parentNode).addClass("active");
					tabs_to_show += ".tab_" + tabname + ", ";
				} else {
					tabs_to_hide += " .tab_" + tabname + ", ";
				}
			});
			$(tabs_to_hide).hide();
			$(tabs_to_show).show();
			
			if (tab_change_callback)
				tab_change_callback(active_tab, is_initial, hash_argument);
		};
	
		// open the default tab
		open_tab(true);
		
		// the change in tab active state is dependent entirely on changes to
		// the window location fragment, since the tabs are made of links
		// with hrefs that are just fragments.
		$(window).bind("hashchange", function() { open_tab(false); });
	});
};

