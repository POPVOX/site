<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd"> 
<html xmlns="http://www.w3.org/1999/xhtml"> 
 
<head profile="http://gmpg.org/xfn/11"> 
	<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" /> 
	<meta http-equiv="X-UA-Compatible" content="IE=EmulateIE8" /><!--[if lte IE 7]><meta http-equiv="X-UA-Compatible" content="chrome=1"><![endif]--> 

	<!--
						  _                                      
		 _| _ _. _  _  __ |_.(_. _   _ _  _ . _  _ _ _. _  _   |_    
		(_|(-_)|(_)| )    |_|| |(_  (-| )(_)|| )(-(-| || )(_)  |_)\/ 
			   _/                       _/               _/      /  
		 ____            _ _                 _   _       _                        
		/ ___|  ___   __| (_)_   _ _ __ ___ | | | | __ _| | ___   __ _  ___ _ __  
		\___ \ / _ \ / _` | | | | | '_ ` _ \| |_| |/ _` | |/ _ \ / _` |/ _ \ '_ \ 
		 ___) | (_) | (_| | | |_| | | | | | |  _  | (_| | | (_) | (_| |  __/ | | |
		|____/ \___/ \__,_|_|\__,_|_| |_| |_|_| |_|\__,_|_|\___/ \__, |\___|_| |_|.com
													  |___/           
	--> 
		

	<title>
	<?php if ( is_front_page() ) : ?>
		<?php bloginfo( 'name'); ?>
	<?php elseif ( is_404() ) : ?>
		<?php _e( 'Page Not Found |', 'titan' ); ?> | <?php bloginfo( 'name'); ?>
	<?php elseif ( is_search() ) : ?>
		<?php printf(__ ("Search results for '%s'", "titan"), attribute_escape(get_search_query())); ?> | <?php bloginfo( 'name'); ?>
	<?php else : ?>
		<?php wp_title($sep = ''); ?> | <?php the_time(__ ( 'F jS, Y', 'titan')); ?> | <?php bloginfo( 'name');?>
	<?php endif; ?>
</title>
	<meta name="description" content=""/>

	<link rel="shortcut icon" href="/media/favicon.ico" />
	
	<link rel="stylesheet" href="/media/master/reset.css" type="text/css" media="screen" /> 
	<link rel="stylesheet" href="/media/master/stylesheet.css" type="text/css" media="screen" /> 
	<link rel="stylesheet" href="/media/master/fonts.css" type="text/css" media="screen" /> 
	
	<script type="text/javascript" src="/media/js/jquery-1.4.2.min.js"></script>
	<script type="text/javascript" src="/media/js/ajaxforms.js"></script>
	
	<link href="/media/css/jquery-ui.css" rel="stylesheet" type="text/css"/>
	<script type="text/javascript" src="/media/js/jquery-ui-1.8rc3.custom.min.js"></script>
	
	<script type="text/javascript" src="/media/tiny_mce/tiny_mce.js"></script>
	<script type="text/javascript">
	tinyMCE.init({
		mode : "none",
		theme : "advanced",
		theme_advanced_buttons1 : "bold,italic,link,unlink,bullist,numlist,blockquote,undo,redo,removeformat,cleanup,code",
		theme_advanced_buttons2 : "",
		theme_advanced_buttons3 : "", 
		theme_advanced_toolbar_location : "top",
		theme_advanced_toolbar_align : "left"});

		
		var login_redirect = '?next=' + document.location;
		
	</script>

	
	<?php if ((is_single() || is_category() || is_page() || is_home()) && (!is_paged())){} else { ?>
		<meta name="robots" content="noindex,follow" />
	<?php } ?>

	<!-- Favicon -->
	<link rel="shortcut icon" href="<?php bloginfo( 'stylesheet_directory'); ?>/images/favicon.ico" />

	<!--Stylesheets-->
	<link href="<?php bloginfo( 'stylesheet_url'); ?>" type="text/css" media="screen" rel="stylesheet" />
	<!--[if lt IE 8]>
	<link rel="stylesheet" type="text/css" media="screen" href="<?php bloginfo( 'template_url'); ?>/stylesheets/ie.css" />
	<![endif]-->
	
	<!--WordPress-->
	<link rel="alternate" type="application/rss+xml" title="<?php bloginfo( 'name'); ?> RSS Feed" href="<?php bloginfo( 'rss2_url'); ?>" />
	<link rel="pingback" href="<?php bloginfo( 'pingback_url'); ?>" />

	<!--WP Hook-->
	<?php if ( is_singular() ) wp_enqueue_script( 'comment-reply' ); ?>
	<?php wp_head(); ?>

	

	
	<script type='text/javascript' src='http://partner.googleadservices.com/gampad/google_service.js'></script>
	<script type='text/javascript'>
		GS_googleAddAdSenseService("ca-pub-4482124597959107");
		GS_googleEnableAllServices();
	</script>
	<script type='text/javascript'>
		
		
	</script>
	<script type='text/javascript'>
		GA_googleFetchAds();
	</script>

	<script type="text/javascript">
	  var _gaq = _gaq || [];
	  _gaq.push(['_setAccount', 'UA-18126194-1']);
	  _gaq.push(['_trackPageview']);
	
	  (function() {
	    var ga = document.createElement('script'); ga.type = 'text/javascript'; ga.async = true;
	    ga.src = ('https:' == document.location.protocol ? 'https://ssl' : 'http://www') + '.google-analytics.com/ga.js';
	    var s = document.getElementsByTagName('script')[0]; s.parentNode.insertBefore(ga, s);
	  })();
	</script>
	
</head>
<body class="land">

<div id="wrap"> 
	
	<div id="head"> 
		<a href="/" id="logo">POPVOX</a>
		<div id="beta">beta</div> 
		
		<div id="head_r">
			<ul id="nav"> 
				
					<li><a href="/accounts/login" onclick="document.location = '/accounts/login' + login_redirect; return false;">Login</a></li>
				
				<li><a href="/blog">Blog</a></li>
				<li><a href="/press">Press</a></li>
				<li><a href="/about" class="last">About</a></li> 
			</ul>
			
			
<h1 id="landing">Your Voice. Verified. Quantified. Amplified</h1>

			
		</div>
	</div><!-- e: head --> 
	
	<div id="page"> 
			
	
		
<div class="blog">
	<div id="header" class="clear">
		<div class="wrapper">
			<?php if (is_home()) { echo( '<h1 id="pagetitle">POPVOX Blog</h1>'); } else { ?><div id="pagetitle"><a href="<?php bloginfo( 'url'); ?>">&lt; Blog Home</a></div><?php } ?>
		</div><!--end wrapper-->
	</div><!--end header-->
	<div class="content-background">
		<div class="wrapper">
			<div class="notice"></div>
			<div id="content">
			
