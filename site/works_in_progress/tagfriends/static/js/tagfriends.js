var tagfriends_ajaxurl = null;
var tagfriends_myfriends = null;

var tagfriends_curcoord = null;

jQuery.fn.tagfriends = function(opts) {
	if (!tagfriends_ajaxurl) {
		alert("Set tagfriends_ajaxurl!");
		return;
	}
	
	if (!tagfriends_myfriends) {
		// Load my friends...
		$.ajax({
			url: tagfriends_ajaxurl,
			data: { cmd: "getfriends" },
			success: function(res) {
				tagfriends_myfriends = res;
			}
		});
	}
	
    return this.each(function(){
    	var node = $(this);
    		
    	if (!node.attr('tagfriends')) return;
    	var photoid = node.attr('tagfriends');	
    	
    	// Add the help box to each image.
    	var callout = $("<div class='tagfriends_callout' style='position: absolute; display: none;'>Click in photo to tag yourself or a friend!</div>");
    	callout.insertAfter(node);
    	
    	var form = $("<div class='tagfriends_friendselector' style='position: absolute; display: none;'><input style='width: 100%' placeholder='Type a friend&apos;s name...'/><div class='tagfriends_friendlist'> </div></div>");
    	form.insertAfter(callout);

    	var inp = form.find('input');
		inp.keyup(function(ev) {
			var txt = inp.val().toLowerCase().split(" ");
			form.find(".tagfriends_friendlist div").each(function() {
				var state = true;
				for (var i = 0; i < txt.length; i++) {
					if (txt[i] == "") continue;
					var f = $(this).text().toLowerCase();
					if (f.indexOf(txt[i]) == -1) state = false;
				}
				$(this).toggle(state);
			});
		});
		inp.keydown(function(ev) {
			if (ev.keyCode == '13') {
				var name = $(this).val();
				if (name.replace(" ", "") == "") return;
				$.ajax({
					url: tagfriends_ajaxurl,
					data: { cmd: "save", photo: photoid, x: tagfriends_curcoord[0], y: tagfriends_curcoord[1], network: "", uid: "", name: name },
					success: function(res) {
						form.hide();
						inp.val("");
						draw_tag(tagfriends_curcoord, null, null, name, true);
					}
				});
			}
		});
    	
    	
    	node.hover(function() {
    		callout.css({left: node.position().left, top: node.position().top});
    		callout.show();
    	}, function() {
    		callout.hide();
    	});
    	
    	$(document).click(function() {
    		form.hide();
    		inp.val("");
    	});
    	
    	function draw_tag(coord, network, uid, name, mine) {
			var tag = $("<div class='tagfriends_tag' style='position: absolute'>◂ <span style='display: none'/> </div>");
			tag.find('span').text(name);
			tag.insertAfter(callout);
			var default_opacity = .55;
    		tag.css({left: node.position().left+coord[0]*node.width() + 25, top: node.position().top+coord[1]*node.height()-tag.height()/2, opacity: default_opacity});
    		tag.hover(function() {
    			tag.css({'z-index': 1});
    			tag.animate({opacity: 1, 'z-index': 1});
    			tag.find('span').show();
    		}, function() {
    			tag.css({'z-index': 0});
    			tag.animate({opacity: default_opacity});
    			tag.find('span').hide();
    		});
    		if (mine) {
    			tag.addClass("tagfriends_mine");
    			tag.css({cursor: "pointer"});
				tag.click(function() {
					if (confirm("Remove tag?")) {
						$.ajax({
							url: tagfriends_ajaxurl,
							data: { cmd: "delete", photo: photoid, network: network, uid: uid, name: name },
							success: function(res) {
								tag.remove();
							}
						});
					}
				});
			}
    	}
    	
		$.ajax({
			url: tagfriends_ajaxurl,
			data: { cmd: "load", photo: photoid },
			success: function(res) {
				for (var i = 0; i < res.length; i++) {
					draw_tag(res[i][0], res[i][1], res[i][2], res[i][3], res[i][4]);
				}
			}
		});
    	
    	// What happens on click.
    	node.click(function(ev) {
    		// convert page coordinate into image coordinate that range from 0 to 1
			var coord = [(ev.pageX-node.offset().left)/node.width(), (ev.pageY-node.offset().top)/node.height()];
			tagfriends_curcoord = coord;
			
			// TODO: show a box at this location?
			
    		form.css({left: node.position().left+coord[0]*node.width() + 10, top: node.position().top+coord[1]*node.height()});
    		form.show();
    		form.find("input").focus();
    		var friendlist = form.find('.tagfriends_friendlist');
    		friendlist.text('');
    		for (var i = 0; i < tagfriends_myfriends.length; i++) {
    			var fr = $('<div/>').text(tagfriends_myfriends[i][2]).attr('tagfriends_friendindex', i);
    			fr.click(function(evt) {
    				var friend = tagfriends_myfriends[$(this).attr('tagfriends_friendindex')];
					$.ajax({
						url: tagfriends_ajaxurl,
						data: { cmd: "save", photo: photoid, x: coord[0], y: coord[1], network: friend[0], uid: friend[1], name: friend[2] },
						success: function(res) {
							draw_tag(coord, friend[0], friend[1], friend[2], true);
							form.hide();
							inp.val("");
						}
					});
    				
    				evt.stopPropagation(); // prevent form.hide() in document.click
    			});
    			friendlist.append(fr);
    		}
			
    		ev.stopPropagation(); // prevent form.hide() in document.click
    	});
    });
}
